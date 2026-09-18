"""Optional MySQL authority for RAG lifecycle metadata.

Chroma remains a rebuildable index. Production should configure this registry with
a database user restricted to ``ai_knowledge_documents``.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pymysql

from app.core.config import get_settings


def enabled() -> bool:
    return bool(get_settings().rag_metadata_mysql_host)


def _mysql_datetime(value: str | None) -> datetime | None:
    """Convert an ISO-8601 instant into the naive UTC value MySQL DATETIME expects."""

    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(tzinfo=None)


@contextmanager
def _connection() -> Iterator[pymysql.Connection | None]:
    settings = get_settings()
    if not settings.rag_metadata_mysql_host:
        yield None
        return
    connection = pymysql.connect(
        host=settings.rag_metadata_mysql_host,
        port=settings.rag_metadata_mysql_port,
        user=settings.rag_metadata_mysql_user,
        password=settings.rag_metadata_mysql_password,
        database=settings.rag_metadata_mysql_database,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=5,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def begin_publish(metadata: dict, *, file_size: int) -> bool:
    with _connection() as connection:
        if connection is None:
            return False
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_knowledge_documents
                  (document_id, version, knowledge_base, original_name, storage_path,
                   content_type, file_size, file_sha256, status, effective_from,
                   expires_at, chunk_count, qdrant_sync_status, uploaded_by,
                   created_at, updated_at)
                VALUES
                  (%s, %s, 'hospital', %s, %s, %s, %s, %s, 'processing', %s,
                   %s, 0, 'reconcile_required', %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
                """,
                (
                    metadata["document_id"], metadata["version"],
                    metadata["source_name"],
                    f"chroma://hospital/{metadata['document_id']}/{metadata['version']}",
                    f"application/{Path(metadata['source_name']).suffix.lstrip('.') or 'octet-stream'}",
                    file_size, metadata["checksum"],
                    _mysql_datetime(metadata["effective_from"]),
                    _mysql_datetime(metadata.get("expires_at")),
                    metadata["uploaded_by"],
                ),
            )
    return True


def list_document_records(document_id: str) -> list[dict]:
    """Return lifecycle revisions from the authoritative metadata registry."""

    with _connection() as connection:
        if connection is None:
            return []
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """SELECT document_id, version, original_name AS source_name,
                          file_sha256 AS checksum, status, effective_from,
                          expires_at, chunk_count, qdrant_sync_status,
                          uploaded_by, updated_at
                   FROM ai_knowledge_documents
                   WHERE document_id=%s
                   ORDER BY version""",
                (document_id,),
            )
            records = list(cursor.fetchall())
    for record in records:
        for key in ("effective_from", "expires_at", "updated_at"):
            value = record.get(key)
            if isinstance(value, datetime):
                record[key] = value.replace(tzinfo=UTC).isoformat()
    return records


def complete_publish(document_id: str, version: int, chunk_count: int) -> None:
    with _connection() as connection:
        if connection is None:
            return
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE ai_knowledge_documents
                   SET status='superseded', updated_at=UTC_TIMESTAMP()
                   WHERE document_id=%s AND version<>%s AND status='active'""",
                (document_id, version),
            )
            cursor.execute(
                """UPDATE ai_knowledge_documents
                   SET status='active', chunk_count=%s, qdrant_sync_status='synced',
                       completed_at=UTC_TIMESTAMP(), updated_at=UTC_TIMESTAMP()
                   WHERE document_id=%s AND version=%s""",
                (chunk_count, document_id, version),
            )


def mark_publish_failed(document_id: str, version: int, message: str) -> None:
    with _connection() as connection:
        if connection is None:
            return
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE ai_knowledge_documents
                   SET status='failed', qdrant_sync_status='reconcile_required',
                       error_message=%s, updated_at=UTC_TIMESTAMP()
                   WHERE document_id=%s AND version=%s""",
                (message[:1000], document_id, version),
            )


def mark_document_status(
    document_id: str, status: str, *, sync_status: str = "synced"
) -> None:
    with _connection() as connection:
        if connection is None:
            return
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE ai_knowledge_documents
                   SET status=%s, qdrant_sync_status=%s, updated_at=UTC_TIMESTAMP(),
                       deleted_at=CASE WHEN %s='deleted' THEN UTC_TIMESTAMP() ELSE deleted_at END
                   WHERE document_id=%s AND status<>'deleted'""",
                (status, sync_status, status, document_id),
            )


def restore_document_statuses(document_id: str, records: list[dict]) -> None:
    """Restore per-version authority state after a failed index mutation."""

    with _connection() as connection:
        if connection is None:
            return
        with connection.cursor() as cursor:
            cursor.executemany(
                """UPDATE ai_knowledge_documents
                   SET status=%s, qdrant_sync_status=%s, updated_at=UTC_TIMESTAMP()
                   WHERE document_id=%s AND version=%s AND status<>'deleted'""",
                [
                    (
                        record.get("status", "inactive"),
                        record.get("qdrant_sync_status", "synced"),
                        document_id,
                        record["version"],
                    )
                    for record in records
                    if isinstance(record.get("version"), int)
                ],
            )


def registry_status() -> dict:
    return {
        "enabled": enabled(),
        "checkedAt": datetime.now(UTC).isoformat(),
        "authority": "mysql" if enabled() else "chroma_only_development",
    }
