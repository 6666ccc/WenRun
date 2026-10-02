"""权限由 Java 登录层决定的院内知识库管理 API。

此 router 只允许内部 API 密钥调用，并要求 Java 为当前用户签发委托令牌。
请求体和 multipart 字段都不能覆盖令牌里的用户身份。
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app.api.dependencies.auth import DelegationContext, verify_api_key, verify_delegation_token
from app.rag.lifecycle import get_rag_service

router = APIRouter(
    prefix="/v1/knowledge",
    tags=["Knowledge"],
    dependencies=[Depends(verify_api_key)],
)

_MANAGE_SCOPE = "knowledge:manage"
_PUBLIC_SCOPE = "knowledge:public"
_STAFF_SCOPE = "knowledge:staff"
_ACCOUNT_TYPES = {"patient", "staff", "internal"}
_SAFE_INLINE_TYPES = {"application/pdf", "image/png", "image/jpeg", "text/plain"}
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_UPLOAD_READ_BYTES = 256 * 1024


def _actor(delegation: DelegationContext) -> dict[str, Any]:
    identity = delegation.identity
    account_type = identity.account_type if identity.account_type in _ACCOUNT_TYPES else "patient"
    return {
        "id": identity.user_id,
        "account_type": account_type,
        "patient_id": identity.patient_id,
        "scopes": tuple(identity.scopes),
    }


def _require_manage(delegation: DelegationContext) -> dict[str, Any]:
    if _MANAGE_SCOPE not in delegation.identity.scopes:
        raise HTTPException(status_code=403, detail="需要知识库管理员权限")
    actor = _actor(delegation)
    # Python 的 lifecycle actor保留真实 account_type；管理员身份由已签名 scope 表示。
    actor["admin"] = True
    return actor


def _require_asset_scope(delegation: DelegationContext, scope: str) -> dict[str, Any]:
    if _MANAGE_SCOPE in delegation.identity.scopes:
        actor = _actor(delegation)
        actor["admin"] = True
        return actor
    if scope == "public" and _PUBLIC_SCOPE in delegation.identity.scopes:
        return _actor(delegation)
    if scope == "staff" and _STAFF_SCOPE in delegation.identity.scopes:
        return _actor(delegation)
    raise HTTPException(status_code=404, detail="知识资料不存在或当前账号无权查看")


def _map_service_error(exc: Exception) -> HTTPException:
    error_name = type(exc).__name__
    if error_name in {"RagConflictError", "RagQualityReviewRequired"}:
        return HTTPException(status_code=409, detail="资料状态已变化，请刷新后重试")
    if error_name == "RagNotFoundError":
        return HTTPException(status_code=404, detail="知识资料不存在或当前账号无权查看")
    if error_name == "RagValidationError":
        return HTTPException(status_code=422, detail=str(exc)[:300])
    if error_name == "RagUnavailableError":
        return HTTPException(status_code=503, detail="知识库服务暂不可用，请稍后重试")
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=404, detail="知识资料不存在或当前账号无权查看")
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail="知识资料不存在")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc)[:300])
    if error_name in {"ConflictError", "LifecycleConflictError"}:
        return HTTPException(status_code=409, detail="资料状态已变化，请刷新后重试")
    if error_name in {"NotFoundError", "LifecycleNotFoundError"}:
        return HTTPException(status_code=404, detail="知识资料不存在或当前账号无权查看")
    return HTTPException(status_code=503, detail="知识库服务暂不可用，请稍后重试")


def _scope_check(actor: dict[str, Any], scope: str, action: str) -> None:
    try:
        allowed = get_rag_service().can_access(actor, scope, action)
    except Exception as exc:  # noqa: BLE001 - permission backend errors must fail closed
        raise HTTPException(status_code=503, detail="知识库权限服务暂不可用") from exc
    if not allowed:
        raise HTTPException(status_code=404, detail="知识资料不存在或当前账号无权查看")


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def submit_document(
    file: UploadFile = File(...),
    document_id: str | None = Form(default=None, alias="documentId", max_length=64),
    effective_from: str | None = Form(default=None, alias="effectiveFrom", max_length=40),
    expires_at: str | None = Form(default=None, alias="expiresAt", max_length=40),
    scope: str = Form(default="public"),
    metadata_json: str | None = Form(default=None, alias="metadata"),
    force_rebuild: bool = Form(default=False, alias="forceRebuild"),
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    """留档并异步创建解析任务，返回 job 回执。"""
    actor = _require_manage(delegation)
    if scope not in {"public", "staff"}:
        raise HTTPException(status_code=400, detail="资料范围只能是 public 或 staff")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename:
        raise HTTPException(status_code=400, detail="请上传带文件名的资料")
    chunks: list[bytes] = []
    total_bytes = 0
    try:
        while True:
            chunk = await file.read(_UPLOAD_READ_BYTES)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > _MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="资料文件不能超过 20 MiB")
            chunks.append(chunk)
    finally:
        await file.close()
    raw = b"".join(chunks)
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata 必须是 JSON 对象")
        _scope_check(actor, scope, "write")
        return await run_in_threadpool(
            get_rag_service().submit,
            raw,
            filename,
            metadata=metadata,
            actor=actor,
            document_id=document_id,
            effective_from=effective_from,
            expires_at=expires_at,
            scope=scope,
            force_rebuild=force_rebuild,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - storage adapters expose heterogeneous errors
        raise _map_service_error(exc) from exc


@router.post("/documents/{document_id}/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def rebuild_document(
    document_id: str,
    file: UploadFile = File(...),
    effective_from: str | None = Form(default=None, alias="effectiveFrom", max_length=40),
    expires_at: str | None = Form(default=None, alias="expiresAt", max_length=40),
    scope: str = Form(default="public"),
    metadata_json: str | None = Form(default=None, alias="metadata"),
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    """为已有逻辑文档创建新文件版本并异步解析。"""
    actor = _require_manage(delegation)
    if scope not in {"public", "staff"}:
        raise HTTPException(status_code=400, detail="资料范围只能是 public 或 staff")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename:
        raise HTTPException(status_code=400, detail="请上传带文件名的资料")
    chunks: list[bytes] = []
    total_bytes = 0
    try:
        while True:
            chunk = await file.read(_UPLOAD_READ_BYTES)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > _MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="资料文件不能超过 20 MiB")
            chunks.append(chunk)
    finally:
        await file.close()
    raw = b"".join(chunks)
    if not raw:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata 必须是 JSON 对象")
        _scope_check(actor, scope, "write")
        return await run_in_threadpool(
            get_rag_service().submit,
            raw,
            filename,
            metadata=metadata,
            actor=actor,
            document_id=document_id,
            effective_from=effective_from,
            expires_at=expires_at,
            scope=scope,
            force_rebuild=True,
            new_revision=True,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.get("/documents")
async def list_knowledge_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    scope: str | None = Query(default=None, pattern="^(public|staff)$"),
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    actor = _require_manage(delegation)
    try:
        if scope:
            _scope_check(actor, scope, "read")
        return await run_in_threadpool(
            get_rag_service().list_documents,
            page=page,
            page_size=page_size,
            scope=scope,
            actor=actor,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.get("/documents/{document_id}")
async def get_knowledge_document(
    document_id: str,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    actor = _require_manage(delegation)
    try:
        return await run_in_threadpool(get_rag_service().get_document, document_id, actor=actor)
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.get("/jobs/{job_id}")
async def get_knowledge_job(
    job_id: str,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    actor = _require_manage(delegation)
    try:
        return await run_in_threadpool(get_rag_service().get_job, job_id, actor=actor)
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_knowledge_job(
    job_id: str,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    actor = _require_manage(delegation)
    try:
        return await run_in_threadpool(get_rag_service().retry, job_id, actor=actor)
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.post("/documents/{document_id}/versions/{version}/review")
async def review_knowledge_document(
    document_id: str,
    version: int,
    decision: str = Form(..., pattern="^(approve|reject)$"),
    reason: str | None = Form(default=None, max_length=2000),
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    actor = _require_manage(delegation)
    try:
        return await run_in_threadpool(
            get_rag_service().review,
            document_id,
            version,
            decision=decision,
            reason=reason,
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.post("/documents/{document_id}/versions/{version}/publish")
async def publish_knowledge_document(
    document_id: str,
    version: int,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> dict[str, Any]:
    actor = _require_manage(delegation)
    try:
        return await run_in_threadpool(
            get_rag_service().publish,
            document_id,
            version,
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc


@router.get("/assets/{asset_id}")
async def get_knowledge_asset(
    asset_id: str,
    scope: str = Query(default="public", pattern="^(public|staff)$"),
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> Response:
    """返回原文件或安全解析产物；实际资源权限由 service 再按当前状态检查。"""
    actor = _require_asset_scope(delegation, scope)
    _scope_check(actor, scope, "read")
    try:
        content, filename, content_type = await run_in_threadpool(
            get_rag_service().read_asset,
            asset_id,
            actor=actor,
        )
    except Exception as exc:  # noqa: BLE001
        raise _map_service_error(exc) from exc
    media_type = content_type.split(";", 1)[0].strip().lower() or "application/octet-stream"
    safe_filename = re.sub(r"[\r\n\"\\]", "_", filename) or "knowledge-source"
    disposition = "inline" if media_type in _SAFE_INLINE_TYPES else "attachment"
    encoded_name = quote(safe_filename, safe="")
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{encoded_name}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )
