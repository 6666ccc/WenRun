"""院内知识库的提交、解析、审核和发布。

上传只留档并排队。后台工人解析出可复核的产物；质量通过后才能写入检索索引。
浏览器不直接调用本模块，入口是带委托令牌的 /v1/knowledge。
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from loguru import logger

from app.rag.chroma import delete_document_points, set_document_status
from app.rag.ingest import SUPPORTED_SUFFIXES, add_hospital_documents
from app.rag.ingestion import IngestionService
from app.rag.ingestion.models import PreparedIngestion, QualityStatus
from app.rag.lifecycle_repository import LeaseLost, LifecycleRepository
from app.rag.lifecycle_storage import AssetStorage, get_asset_storage

_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
IndexWriter = Callable[[list, list[str] | None], list[str]]
StatusWriter = Callable[..., None]


class RagNotFoundError(LookupError):
    """资料不存在，或当前身份不能知道它存在。"""


class RagConflictError(RuntimeError):
    """版本状态已经变化，调用方需要刷新后再操作。"""


class RagQualityReviewRequired(RagConflictError):
    """质量报告阻止发布，必须先修复或重新解析。"""


class RagValidationError(ValueError):
    """请求参数或文件内容不符合入库规则。"""


class RagUnavailableError(RuntimeError):
    """索引或存储暂时不可用。"""


def _timestamp(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RagValidationError(f"{field} 必须是 ISO-8601 时间") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def published_revision_keys(
    scopes: tuple[str, ...] = ("public",), *, now: datetime | None = None
) -> set[tuple[str, int]] | None:
    """返回当前对调用方可见的已发布版本。登记不可用时返回 None，由检索侧拒绝新片段。"""
    try:
        rows = LifecycleRepository.from_environment().authority_rows(scopes, now=now)
    except Exception as exc:  # noqa: BLE001 - retrieval must fail closed for governed chunks
        logger.warning("rag_authority_lookup_failed error={}", type(exc).__name__)
        return None
    return {(str(row["document_id"]), int(row["version"])) for row in rows}


def _parse_instant(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_effective_now(version: dict, now: datetime) -> bool:
    """只有已经生效的 active 版本才对非管理员公开。scheduled 和未来版本都不可读。"""
    if version.get("status") != "active":
        return False
    current = now.astimezone(UTC)
    effective = _parse_instant(version.get("effective_from"))
    expires = _parse_instant(version.get("expires_at"))
    if effective is None or effective > current:
        return False
    return expires is None or expires > current


def _actor_id(actor: dict[str, Any]) -> str:
    return str(actor.get("id") or "0")


class RagLifecycleService:
    """连接版本库、原文件存储、解析流水线和检索索引。"""

    def __init__(
        self,
        *,
        repository: LifecycleRepository | None = None,
        storage: AssetStorage | None = None,
        ingestion: IngestionService | None = None,
        index_documents: IndexWriter | None = None,
        set_status: StatusWriter | None = None,
        delete_points: Callable[..., None] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.repository = repository or LifecycleRepository.from_environment()
        self.storage = storage or get_asset_storage()
        self.ingestion = ingestion or IngestionService()
        self.index_documents = index_documents or add_hospital_documents
        self.set_status = set_status or set_document_status
        self.delete_points = delete_points or delete_document_points
        self.worker_id = worker_id or f"rag-{os.getpid()}"
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def ensure_ready(self) -> None:
        self.repository.initialize()
        # Production initialize() does not create tables. Verify migrations and
        # connectivity before accepting traffic, rather than hiding worker errors.
        with self.repository.connection() as connection:
            cursor = connection.cursor()
            for table, column in (
                ("rag_documents", "document_id"), ("rag_versions", "version"),
                ("rag_builds", "build_id"), ("rag_jobs", "fence"),
                ("rag_assets", "asset_id"),
            ):
                self.repository._execute(cursor, f"SELECT {column} FROM {table} LIMIT 1")

    def is_ready(self) -> bool:
        if self._thread is None or not self._thread.is_alive():
            return False
        self.ensure_ready()
        return True

    def can_access(self, actor: dict[str, Any], scope: str, action: str) -> bool:
        if scope not in {"public", "staff"}:
            return False
        scopes = set(actor.get("scopes") or ())
        if actor.get("admin") or "knowledge:manage" in scopes:
            return True
        if action != "read":
            return False
        if scope == "public":
            return "knowledge:public" in scopes
        return "knowledge:staff" in scopes

    def submit(
        self,
        content: bytes,
        filename: str,
        *,
        metadata: dict | None = None,
        actor: dict[str, Any],
        document_id: str | None = None,
        effective_from: str | None = None,
        expires_at: str | None = None,
        scope: str = "public",
        force_rebuild: bool = False,
        new_revision: bool = False,
    ) -> dict[str, Any]:
        """保存原文件并创建解析任务。内容未变时复用已有版本。"""
        safe_name = Path(filename.replace("\\", "/")).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
            raise RagValidationError(f"不支持的文件格式：{suffix or '无扩展名'}，支持：{supported}")
        if not content:
            raise RagValidationError("上传文件不能为空")
        logical_id = (document_id or str(uuid5(NAMESPACE_URL, f"wenrun-hospital:{safe_name.casefold()}"))).strip()
        if not logical_id or len(logical_id) > 64:
            raise RagValidationError("documentId 不能为空且不能超过64字符")
        effective = _timestamp(effective_from, "effectiveFrom") or datetime.now(UTC).isoformat()
        expires = _timestamp(expires_at, "expiresAt")
        if expires is not None and expires <= effective:
            raise RagValidationError("expiresAt 必须晚于 effectiveFrom")
        checksum = sha256(content).hexdigest()
        if not force_rebuild and not new_revision:
            existing = self.repository.find_duplicate(
                checksum=checksum, scope=scope, document_id=logical_id,
            )
            if existing is not None:
                return {
                    "document_id": existing["document_id"],
                    "version": int(existing["version"]),
                    "build_id": existing.get("build_id"),
                    "job_id": existing.get("job_id"),
                    "status": existing["status"],
                    "idempotent": True,
                }
        storage_key, stored_checksum = self.storage.put(content, suffix=suffix.lstrip("."))
        if stored_checksum != checksum:
            raise RagUnavailableError("原文件校验失败")
        asset_id = str(uuid4())
        source_asset = {
            "asset_id": asset_id,
            "storage_key": storage_key,
            "file_name": safe_name,
            "content_type": _CONTENT_TYPES.get(suffix, "application/octet-stream"),
            "file_size": len(content),
            "checksum": checksum,
        }
        version = 0
        rebuild_current = force_rebuild and not new_revision
        if rebuild_current:
            latest = self.repository.get_latest(logical_id)
            if latest is None:
                rebuild_current = False
            else:
                version = int(latest["version"])
        try:
            receipt = self.repository.create_submission(
                document_id=logical_id,
                version=version,
                build_id=str(uuid4()),
                job_id=str(uuid4()),
                source_asset=source_asset,
                scope=scope,
                metadata=dict(metadata or {}),
                effective_from=effective,
                expires_at=expires,
                actor_id=_actor_id(actor),
                force_rebuild=rebuild_current,
            )
        except Exception as exc:
            self.storage.delete(storage_key)
            if isinstance(exc, (RagValidationError, RagNotFoundError, RagConflictError)):
                raise
            logger.warning("rag_submit_failed document_id={} error={}", logical_id, type(exc).__name__)
            raise RagUnavailableError("知识库暂时无法接收资料") from exc
        receipt["idempotent"] = False
        self._wake.set()
        return receipt

    def process_once(self) -> bool:
        """领取一个解析任务。没有任务时返回 False。"""
        job = self.repository.claim_job(self.worker_id, lease_seconds=180)
        if not job:
            return False
        source = job.get("source") or {}
        try:
            if not source.get("storage_key"):
                raise RagUnavailableError("source file is missing")
            raw = self.storage.get(source["storage_key"])
            extra = self.repository._load(source.get("metadata_json"), {})
            if not isinstance(extra, dict):
                extra = {}
            prepared = self.ingestion.prepare(
                raw,
                document_id=job["document_id"],
                file_name=source.get("source_name") or source.get("file_name"),
                metadata={
                    **extra,
                    "document_id": job["document_id"],
                    "version": int(job["version"]),
                    "checksum": source.get("checksum"),
                    "scope": source.get("scope") or "public",
                    "effective_from": source.get("effective_from"),
                    "expires_at": source.get("expires_at"),
                    "file_type": Path(source.get("file_name") or "").suffix.lower(),
                    "source_asset_id": job["source_asset_id"],
                },
            )
            self._store_artifact(job, prepared)
        except LeaseLost:
            logger.info("rag_job_lease_lost job_id={}", job["job_id"])
        except Exception as exc:  # noqa: BLE001 - worker must record and continue
            logger.warning(
                "rag_job_failed job_id={} error={}", job["job_id"], type(exc).__name__,
            )
            self.repository.fail_job(
                job_id=job["job_id"],
                fence=int(job["fence"]),
                worker_id=self.worker_id,
                error_code=type(exc).__name__,
                retry_delay_seconds=15,
            )
        return True

    def _store_artifact(self, job: dict, prepared: PreparedIngestion) -> None:
        payload = json.dumps(prepared.to_dict(), ensure_ascii=False).encode("utf-8")
        storage_key, checksum = self.storage.put(payload, suffix="json")
        quality_state = "built" if prepared.quality_report.status == QualityStatus.PASS else "needs_review"
        asset = {
            "asset_id": str(uuid4()),
            "storage_key": storage_key,
            "file_name": f"{job['document_id']}-v{job['version']}.json",
            "content_type": "application/json",
            "file_size": len(payload),
            "checksum": checksum,
        }
        try:
            stored = self.repository.register_artifact(
                asset=asset,
                build_id=job["build_id"],
                quality=prepared.to_dict()["quality_report"],
                parser_fingerprint=f"{prepared.parsed_document.parser}:{prepared.parsed_document.parser_version}",
                embedding_fingerprint=os.getenv("EMBEDDING_MODEL") or "deferred",
                chunk_count=len(prepared.chunks),
                quality_state=quality_state,
                job_id=job["job_id"],
                fence=int(job["fence"]),
                worker_id=self.worker_id,
            )
        except Exception:
            self.storage.delete(storage_key)
            raise
        if not stored:
            self.storage.delete(storage_key)

    def list_documents(self, *, page: int, page_size: int, scope: str | None, actor: dict) -> dict:
        del actor
        result = self.repository.list_documents(page=page, page_size=page_size, scope=scope)
        for item in result["items"]:
            item["metadata"] = self.repository._load(item.pop("metadata_json", None), {})
        return result

    def get_document(self, document_id: str, *, actor: dict) -> dict:
        del actor
        document = self.repository.get_document(document_id)
        if not document["versions"]:
            raise RagNotFoundError(document_id)
        return document

    def get_job(self, job_id: str, *, actor: dict) -> dict:
        del actor
        job = self.repository.get_job(job_id)
        if not job:
            raise RagNotFoundError(job_id)
        if "quality_json" in job:
            job["quality_report"] = self.repository._load(job.pop("quality_json"), None)
        return job

    def retry(self, job_id: str, *, actor: dict) -> dict:
        try:
            result = self.repository.retry_job(job_id, _actor_id(actor))
        except KeyError as exc:
            raise RagNotFoundError(job_id) from exc
        except ValueError as exc:
            raise RagConflictError(str(exc)) from exc
        self._wake.set()
        return result

    def review(
        self,
        document_id: str,
        version: int,
        *,
        decision: str,
        reason: str | None,
        actor: dict,
    ) -> dict:
        try:
            return self.repository.decision(
                document_id,
                version,
                decision=decision,
                actor_id=_actor_id(actor),
                reason=reason or "",
            )
        except KeyError as exc:
            raise RagNotFoundError(document_id) from exc
        except ValueError as exc:
            message = str(exc)
            if "blocks publication" in message:
                raise RagQualityReviewRequired(message) from exc
            raise RagConflictError(message) from exc

    def publish(self, document_id: str, version: int, *, actor: dict) -> dict:
        document = self.get_document(document_id, actor=actor)
        row = next((item for item in document["versions"] if int(item["version"]) == version), None)
        if row is None:
            raise RagNotFoundError(document_id)
        if row["status"] in {"active", "scheduled"}:
            effective = _parse_instant(row.get("effective_from"))
            expires = _parse_instant(row.get("expires_at"))
            now = datetime.now(UTC)
            if row["status"] == "scheduled" and effective is not None and effective <= now and (expires is None or expires > now):
                # Make due vectors visible first. Authority lookup still gates
                # access; failure leaves the scheduled row durable for retry.
                self.set_status(document_id, "active", version=version)
                result = self.repository.publish(document_id, version, _actor_id(actor))
                for previous in document["versions"]:
                    if previous["status"] == "active" and int(previous["version"]) != version:
                        self.set_status(document_id, "superseded", version=int(previous["version"]))
                return {**result, "idempotent": False}
            try:
                self.set_status(document_id, row["status"], version=version)
            except Exception as exc:  # noqa: BLE001 - heal a publish that committed before the index flip
                logger.warning(
                    "rag_publish_status_repair_failed document_id={} error={}",
                    document_id, type(exc).__name__,
                )
            return {
                "document_id": document_id,
                "version": version,
                "build_id": row.get("active_build_id"),
                "status": row["status"],
                "idempotent": True,
            }
        if row["status"] not in {"approved", "built"}:
            raise RagConflictError("只有审核通过的版本可以发布")
        build = next(
            (
                item for item in row.get("builds") or []
                if item.get("artifact_asset_id") and item.get("status") in {"built", "approved"}
            ),
            None,
        )
        if build is None:
            raise RagConflictError("解析产物尚未就绪")
        artifact = self.repository.asset(build["artifact_asset_id"])
        if artifact is None:
            raise RagUnavailableError("解析产物不存在")
        try:
            prepared = PreparedIngestion.from_dict(
                json.loads(self.storage.get(artifact["storage_key"]).decode("utf-8"))
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise RagUnavailableError("解析产物无法读取") from exc
        documents = prepared.to_documents()
        if not documents:
            raise RagQualityReviewRequired("该版本没有可发布的检索片段")
        chunk_ids = [
            str(uuid5(NAMESPACE_URL, f"{document_id}:{version}:{index}"))
            for index in range(len(documents))
        ]
        now = datetime.now(UTC).isoformat()
        for index, chunk in enumerate(documents):
            chunk.metadata.update({
                "document_id": document_id,
                "source_name": row["source_name"],
                "checksum": row["checksum"],
                "version": version,
                "status": "pending",
                "effective_from": row["effective_from"],
                "expires_at": row.get("expires_at") or "",
                "scope": row["scope"],
                "build_id": build["build_id"],
                "source_asset_id": row["source_asset_id"],
                "updated_at": now,
                "metadata_schema": "rag-metadata-v2",
                "chunk_id": chunk_ids[index],
                "chunk_count": len(documents),
            })
        previous = [
            (int(item["version"]), item["status"])
            for item in document["versions"]
            if item["status"] == "active" and int(item["version"]) != version
        ]
        written = False
        try:
            self.index_documents(documents, chunk_ids)
            written = True
            result = self.repository.publish(document_id, version, _actor_id(actor))
        except Exception as exc:
            if written:
                try:
                    self.delete_points(document_id, version=version)
                except Exception as rollback_exc:  # noqa: BLE001
                    logger.warning(
                        "rag_publish_rollback_failed document_id={} error={}",
                        document_id, type(rollback_exc).__name__,
                    )
            if isinstance(exc, (RagConflictError, RagNotFoundError, RagValidationError, KeyError, ValueError)):
                if isinstance(exc, KeyError):
                    raise RagNotFoundError(document_id) from exc
                if isinstance(exc, ValueError):
                    raise RagConflictError(str(exc)) from exc
                raise
            logger.warning("rag_publish_failed document_id={} error={}", document_id, type(exc).__name__)
            raise RagUnavailableError("发布到检索索引失败") from exc
        try:
            self.set_status(document_id, result["status"], version=version)
            if result["status"] == "active":
                for old_version, _old_status in previous:
                    self.set_status(document_id, "superseded", version=old_version)
        except Exception as exc:
            logger.warning(
                "rag_publish_visibility_failed document_id={} error={}",
                document_id, type(exc).__name__,
            )
            raise RagUnavailableError("发布登记已写入，但检索索引尚未公开") from exc
        result["idempotent"] = False
        return result

    def read_asset(self, asset_id: str, *, actor: dict) -> tuple[bytes, str, str]:
        row = self.repository.asset(asset_id)
        if row is None or not self.can_access(actor, row["scope"], "read"):
            raise RagNotFoundError(asset_id)
        document = self.repository.get_document(row["document_id"])
        version = next(
            (item for item in document["versions"] if int(item["version"]) == int(row["version"])),
            None,
        )
        published = version is not None and _is_effective_now(version, datetime.now(UTC))
        if not published and not actor.get("admin") and "knowledge:manage" not in set(actor.get("scopes") or ()):
            raise RagNotFoundError(asset_id)
        try:
            content = self.storage.get(row["storage_key"])
        except OSError as exc:
            raise RagNotFoundError(asset_id) from exc
        return content, row["file_name"], row["content_type"]

    def start_worker(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run_worker, name="rag-lifecycle", daemon=True,
        )
        self._thread.start()

    def stop_worker(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def _run_worker(self) -> None:
        next_activation = 0.0
        while not self._stop.is_set():
            try:
                if monotonic() >= next_activation:
                    self.activate_due_publications()
                    next_activation = monotonic() + 30
                worked = self.process_once()
            except Exception:  # noqa: BLE001 - keep the worker alive
                logger.exception("rag_worker_iteration_failed")
                worked = False
            if not worked:
                self._wake.wait(2)
                self._wake.clear()

    def activate_due_publications(self) -> int:
        """Due scheduled rows survive failures and are retried after restart."""
        activated = 0
        actor = {"id": "scheduler", "admin": True, "scopes": ("knowledge:manage",)}
        for row in self.repository.authority_rows(("public", "staff")):
            if row["status"] != "scheduled":
                continue
            try:
                self.publish(row["document_id"], int(row["version"]), actor=actor)
                activated += 1
            except Exception as exc:  # noqa: BLE001 - retry failed publication next cycle
                logger.warning("rag_scheduled_activation_failed document_id={} error={}", row["document_id"], type(exc).__name__)
        return activated


@lru_cache
def get_rag_service() -> RagLifecycleService:
    return RagLifecycleService()
