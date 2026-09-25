"""院内知识文档的发布与版本管理入口。

上传文件先解析、清理、分类、切成小段，再生成向量存入 Chroma 供相似度检索。
同一文档可以有多个版本；新版本成功发布后旧版本才失效。可选的 MySQL registry
记录权威版本状态，Chroma 则是可重建的检索索引。
"""

from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from loguru import logger

from app.rag.chroma import (
    delete_document_points,
    ensure_collection,
    get_chroma_client,
    get_embeddings,
    get_store,
    hospital_collection,
    sanitize_chroma_metadata,
    set_document_status,
)
from app.rag.chroma import (
    list_document_records as list_chroma_document_records,
)
from app.rag.ingestion import IngestionService
from app.rag.registry import (
    begin_publish,
    complete_publish,
    mark_document_status,
    mark_publish_failed,
)
from app.rag.registry import (
    enabled as registry_enabled,
)
from app.rag.registry import (
    list_document_records as list_registry_document_records,
)
from app.rag.registry import (
    restore_document_statuses as restore_registry_document_statuses,
)

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}


def _document_records(document_id: str) -> list[dict]:
    """优先从 MySQL 版本登记表读取；未启用时从 Chroma 元数据读取。"""
    if registry_enabled():
        return list_registry_document_records(document_id)
    return list_chroma_document_records(document_id)


def _normalize_timestamp(value: str | None, *, field: str) -> str | None:
    """把上传参数中的时间统一转成 UTC，供版本生效/过期判断使用。"""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} 必须是 ISO-8601 时间") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


# 步骤一：读取上传文件的二进制内容，并检查扩展名。
def _read_file(file: bytes | bytearray | BinaryIO, filename: str) -> bytes:
    """检查上传格式并统一读取为字节，再交给预处理器解析。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(f"不支持的文件格式：{suffix}，支持：{supported}")

    if isinstance(file, (bytes, bytearray)):
        return bytes(file)

    read = getattr(file, "read", None)
    if not callable(read):
        raise TypeError("file 必须是 bytes 或可读取的二进制文件对象")

    data = read()
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


@lru_cache
def _get_ingestion_service() -> IngestionService:
    """首次真正上传时才创建预处理器，避免聊天服务导入时加载分词模型。"""

    return IngestionService()


# 步骤四：把切好的 Document 写入医院知识库。
def add_hospital_documents(
    documents: list[Document],
    ids: list[str] | None = None,
) -> list[str]:
    """把清理过元数据的文档片段写进院内向量集合。"""
    if not documents:
        raise ValueError("没有可写入的文档片段")

    client = get_chroma_client()
    embeddings = get_embeddings()
    ensure_collection(client, hospital_collection)
    store = get_store(client, hospital_collection, embeddings)
    prepared = [
        Document(
            page_content=document.page_content,
            metadata=sanitize_chroma_metadata(document.metadata),
        )
        for document in documents
    ]
    return store.add_documents(documents=prepared, ids=ids)


# 完整执行一次文件载入：读取、解析、切块、embedding 并写入 Chroma。
def ingest_file(
    file: bytes | bytearray | BinaryIO,
    filename: str,
    **lifecycle: object,
) -> dict:
    """上传接口的简短入口，实际发布与版本处理交给 publish_document。"""
    return publish_document(file, filename, **lifecycle)


def publish_document(
    file: bytes | bytearray | BinaryIO,
    filename: str,
    *,
    document_id: str | None = None,
    uploaded_by: int = 0,
    effective_from: str | None = None,
    expires_at: str | None = None,
    force_rebuild: bool = False,
) -> dict:
    """发布一个文档版本；内容未变化时复用已有版本，成功后替换旧版本。"""

    data = _read_file(file, filename)
    checksum = sha256(data).hexdigest()
    logical_id = document_id or str(
        uuid5(NAMESPACE_URL, f"wenrun-hospital:{filename.casefold()}")
    )
    if not logical_id.strip() or len(logical_id) > 64:
        raise ValueError("documentId 不能为空且不能超过64字符")
    normalized_effective = _normalize_timestamp(
        effective_from, field="effectiveFrom"
    )
    normalized_expires = _normalize_timestamp(expires_at, field="expiresAt")
    if normalized_expires is not None:
        expiry = datetime.fromisoformat(normalized_expires)
        effective = (
            datetime.fromisoformat(normalized_effective)
            if normalized_effective
            else datetime.now(UTC)
        )
        if expiry <= effective:
            raise ValueError("expiresAt 必须晚于 effectiveFrom")
    existing = _document_records(logical_id)
    if not force_rebuild:
        # 文件内容的 SHA-256 相同就不重复生成向量，也不增加版本号。
        duplicate = next(
            (
                item
                for item in reversed(existing)
                if item.get("checksum") == checksum
                and item.get("status") not in {"failed", "deleting", "deleted"}
            ),
            None,
        )
        if duplicate is not None:
            return {
                "document_id": logical_id,
                "filename": duplicate.get("source_name") or filename,
                "checksum": checksum,
                "version": duplicate.get("version", 1),
                "status": duplicate.get("status", "active"),
                "chunk_count": duplicate.get("chunk_count", 0),
                "idempotent": True,
            }

    now = datetime.now(UTC).isoformat()
    version = max(
        (item.get("version", 0) for item in existing if isinstance(item.get("version"), int)),
        default=0,
    ) + 1
    metadata = {
        "source_name": filename,
        "file_type": Path(filename).suffix.lower(),
        "document_id": logical_id,
        "checksum": checksum,
        "version": version,
        "status": "active",
        "effective_from": normalized_effective or now,
        "expires_at": normalized_expires,
        "uploaded_by": uploaded_by,
        "updated_at": now,
        "metadata_schema": "rag-metadata-v2",
    }
    chunks = _get_ingestion_service().ingest(
        data,
        document_id=logical_id,
        file_name=filename,
        metadata=metadata,
    )
    if not chunks:
        raise ValueError("文件切分后没有可写入的文本片段")

    # 使用稳定 UUID 作为 chunk ID，便于按文档版本覆盖与删除。
    chunk_ids = [
        str(uuid5(NAMESPACE_URL, f"{logical_id}:{version}:{index}"))
        for index in range(len(chunks))
    ]
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = chunk_ids[index]
        chunk.metadata["chunk_count"] = len(chunks)

    changed: list[tuple[int, str]] = []
    written_ids: list[str] = []
    registry_started = False
    try:
        # 先登记“处理中”，再写向量；全部完成后才把旧版本标记为被替代。
        registry_started = begin_publish(metadata, file_size=len(data))
        written_ids = add_hospital_documents(chunks, ids=chunk_ids)
        for record in existing:
            old_version = record.get("version")
            old_status = record.get("status")
            if isinstance(old_version, int) and old_status == "active":
                set_document_status(logical_id, "superseded", version=old_version)
                changed.append((old_version, old_status))
        complete_publish(logical_id, version, len(written_ids))
    except Exception as exc:
        # 发布中途失败时撤销新向量、恢复旧版本状态，避免半成品进入检索。
        if written_ids:
            delete_document_points(logical_id, version=version)
        for old_version, old_status in changed:
            set_document_status(logical_id, old_status, version=old_version)
        if registry_started:
            try:
                mark_publish_failed(logical_id, version, type(exc).__name__)
            except Exception as registry_exc:  # noqa: BLE001 - preserve original failure
                # 连“发布失败”标记都写不进去时，仍向调用方保留最初的发布异常。
                logger.warning(
                    "rag_registry_failure_marker_failed document_id={} version={} error={}",
                    logical_id,
                    version,
                    type(registry_exc).__name__,
                )
        raise

    return {
        "document_id": logical_id,
        "filename": filename,
        "checksum": checksum,
        "version": version,
        "status": "active",
        "chunk_count": len(written_ids),
        "idempotent": False,
    }


def get_document_versions(document_id: str) -> list[dict]:
    """列出一份文档的所有已登记版本及状态。"""
    return _document_records(document_id)


def deactivate_document(document_id: str) -> int:
    """停用当前有效版本，让后续检索不再使用它们。"""
    records = _document_records(document_id)
    active = [item for item in records if item.get("status") == "active"]
    changed: list[int] = []
    try:
        for record in active:
            version = record.get("version")
            if isinstance(version, int):
                set_document_status(document_id, "inactive", version=version)
                changed.append(version)
        if active:
            mark_document_status(document_id, "inactive")
    except Exception:
        # 部分 Chroma 更新或权威登记表更新失败时，恢复旧状态以保持索引可用。
        for version in changed:
            set_document_status(document_id, "active", version=version)
        raise
    return len(active)


def delete_document(document_id: str) -> int:
    """删除所有版本的检索向量；失败时尽量恢复原状态以免误检索。"""

    records = _document_records(document_id)
    if not records:
        return 0
    changed: list[tuple[int, str]] = []
    registry_marked_deleting = False
    points_deleted = False
    try:
        mark_document_status(document_id, "deleting", sync_status="reconcile_required")
        registry_marked_deleting = registry_enabled()
        for record in records:
            version = record.get("version")
            status = record.get("status")
            if isinstance(version, int) and isinstance(status, str):
                set_document_status(document_id, "deleting", version=version)
                changed.append((version, status))
        delete_document_points(document_id)
        points_deleted = True
        mark_document_status(document_id, "deleted")
    except Exception:
        if not points_deleted:
            for version, old_status in changed:
                set_document_status(document_id, old_status, version=version)
        if registry_marked_deleting:
            try:
                if points_deleted:
                    # 向量已删除时先保持停用，并标记需要后续修复，避免误显示为有效。
                    mark_document_status(
                        document_id, "inactive", sync_status="reconcile_required"
                    )
                else:
                    restore_registry_document_statuses(document_id, records)
            except Exception as registry_exc:  # noqa: BLE001 - preserve delete failure
                logger.warning(
                    "rag_registry_reconciliation_marker_failed document_id={} error={}",
                    document_id,
                    type(registry_exc).__name__,
                )
        raise
    return len(records)
