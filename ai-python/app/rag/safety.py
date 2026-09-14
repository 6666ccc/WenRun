"""Fail-closed safety checks for untrusted RAG chunks."""

import re
from datetime import UTC, datetime

from langchain_core.documents import Document

RAG_SAFETY_SCHEMA_VERSION = "rag-safety-v1"
MAX_RAG_CHUNK_CHARS = 4_000

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PROMPT_INJECTION = re.compile(
    r"(?i)(ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"system\s+prompt|developer\s+message|jailbreak|"
    r"忽略.{0,12}(系统|之前|以上).{0,8}(指令|提示)|"
    r"你现在是.{0,30}(助手|系统)|执行以下命令|泄露.{0,12}(密钥|提示词))"
)


def sanitize_rag_text(value: str, *, limit: int = MAX_RAG_CHUNK_CHARS) -> str:
    """Remove non-printing controls and enforce a per-chunk character ceiling."""

    cleaned = _CONTROL_CHARACTERS.sub("", value).replace("\r\n", "\n").strip()
    return cleaned[:limit]


def has_prompt_injection_risk(value: str) -> bool:
    return bool(_PROMPT_INJECTION.search(value))


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_active_document(metadata: dict, *, now: datetime | None = None) -> bool:
    """Only explicitly active and currently effective lifecycle records are usable."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    if metadata.get("status") != "active":
        return False
    effective = _parse_time(metadata.get("effective_from"))
    expires = _parse_time(metadata.get("expires_at"))
    if effective is None or effective > current:
        return False
    return expires is None or expires > current


def prepare_rag_documents(
    documents: list[Document], *, now: datetime | None = None
) -> tuple[list[Document], int]:
    """Return safe active chunks and the count rejected for injection risk."""

    safe: list[Document] = []
    rejected = 0
    for document in documents:
        metadata = dict(document.metadata or {})
        if not is_active_document(metadata, now=now):
            continue
        content = sanitize_rag_text(document.page_content)
        if not content or has_prompt_injection_risk(content):
            rejected += 1
            continue
        metadata["safety_schema"] = RAG_SAFETY_SCHEMA_VERSION
        safe.append(Document(page_content=content, metadata=metadata))
    return safe, rejected
