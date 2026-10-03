"""院内检索结果进入模型前的最后一道筛选。

只有状态有效、在生效期内、正文非空且未命中明显提示注入文本的片段才保留。
文档正文是参考资料，即使包含“忽略指令”之类的话也不能改变助手规则。
"""

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
    """识别常见的“让模型改听文档指令”文本。"""
    return bool(_PROMPT_INJECTION.search(value))


def _parse_time(value: object) -> datetime | None:
    """把文档元数据里的时间转为 UTC；缺失或格式错误时返回空值。"""
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


def _is_governed(metadata: dict) -> bool:
    """新发布流程写入的片段带有范围或构建号，必须再对发布登记。"""
    scope = metadata.get("scope")
    return bool(
        metadata.get("build_id")
        or metadata.get("source_asset_id")
        or scope in {"public", "staff"}
    )


def _revision_key(metadata: dict) -> tuple[str, int] | None:
    document_id = metadata.get("document_id")
    version = metadata.get("version")
    if isinstance(version, float) and version.is_integer():
        version = int(version)
    if isinstance(version, str) and version.isdigit():
        version = int(version)
    if (
        not isinstance(document_id, str)
        or not document_id
        or not isinstance(version, int)
    ):
        return None
    return document_id, version


def _published_keys(
    scopes: tuple[str, ...], now: datetime
) -> set[tuple[str, int]] | None:
    from app.rag.lifecycle import published_revision_keys

    return published_revision_keys(scopes, now=now)


def prepare_rag_documents(
    documents: list[Document],
    *,
    now: datetime | None = None,
    scopes: tuple[str, ...] = ("public",),
    authority_keys: set[tuple[str, int]] | None = None,
) -> tuple[list[Document], int]:
    """返回可供回答的资料片段，以及因风险文本被丢弃的数量。

    患者默认只看 public。带发布标记的片段还必须出现在当前生效的发布登记里。
    登记不可用时，这些新片段一律不进入回答；没有该标记的旧索引仍按原规则保留。
    """

    current = (now or datetime.now(UTC)).astimezone(UTC)
    governed = any(
        _is_governed(dict(document.metadata or {})) for document in documents
    )
    keys = authority_keys
    if governed and keys is None:
        keys = _published_keys(scopes, current)
    safe: list[Document] = []
    rejected = 0
    for document in documents:
        metadata = dict(document.metadata or {})
        if not is_active_document(metadata, now=current):
            continue
        scope = metadata.get("scope") or ""
        if scope == "staff" and "staff" not in scopes:
            continue
        if _is_governed(metadata):
            identity = _revision_key(metadata)
            if keys is None or identity is None or identity not in keys:
                continue
        content = sanitize_rag_text(document.page_content)
        if not content or has_prompt_injection_risk(content):
            rejected += 1
            continue
        metadata["safety_schema"] = RAG_SAFETY_SCHEMA_VERSION
        metadata["source_text_truncated"] = (
            len(document.page_content.strip()) > MAX_RAG_CHUNK_CHARS
        )
        safe.append(Document(page_content=content, metadata=metadata))
    return safe, rejected
