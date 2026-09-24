"""文档发布生命周期：结构化预处理 → Chroma，并同步 registry。"""

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
    if registry_enabled():
        return list_registry_document_records(document_id)
    return list_chroma_document_records(document_id)


def _normalize_timestamp(value: str | None, *, field: str) -> str | None:
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
    """Construct the new preprocessor lazily so app imports load no ML runtime."""

    return IngestionService()


# 步骤四：把切好的 Document 写入医院知识库。
def add_hospital_documents(
    documents: list[Document],
    ids: list[str] | None = None,
) -> list[str]:
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
    """Publish one version, idempotently by checksum, then supersede older versions."""

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
        # Compensate partial publication: remove the new points and restore any
        # older versions changed before the failure.
        if written_ids:
            delete_document_points(logical_id, version=version)
        for old_version, old_status in changed:
            set_document_status(logical_id, old_status, version=old_version)
        if registry_started:
            try:
                mark_publish_failed(logical_id, version, type(exc).__name__)
            except Exception as registry_exc:  # noqa: BLE001 - preserve original failure
                # The failed registry write is itself reconciliation work; preserve
                # the original publication failure for the caller.
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
    return _document_records(document_id)


def deactivate_document(document_id: str) -> int:
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
        # Keep the vector index usable when either a partial Chroma update or
        # the authoritative registry update fails.
        for version in changed:
            set_document_status(document_id, "active", version=version)
        raise
    return len(active)


def delete_document(document_id: str) -> int:
    """Delete all vector points, restoring statuses if Chroma deletion fails."""

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
                    # The index is already gone: stay fail-closed and queue repair.
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
