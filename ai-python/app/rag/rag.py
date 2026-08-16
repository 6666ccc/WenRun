from dataclasses import dataclass, field
from typing import Any

from app.rag.collections import COLLECTIONS, KnowledgeBase

_vector_stores = None


def set_vector_stores(stores) -> None:
    """Inject a store registry for tests. Pass None to restore the default factory."""
    global _vector_stores
    _vector_stores = stores


def get_injected_vector_stores():
    return _vector_stores


@dataclass
class ScoredChunk:
    content: str
    score: float
    document_id: str = ""
    title: str = ""
    page: int | None = None
    section: str | None = None
    knowledge_base: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def retrieve(base: KnowledgeBase, query: str, filters: dict | None = None) -> list[ScoredChunk]:
    if not isinstance(base, KnowledgeBase):
        raise TypeError("retrieve accepts KnowledgeBase only, not a raw collection string")
    collection = COLLECTIONS[base]
    store = _resolve_store(base, collection)
    pairs = store.similarity_search_with_score(query, k=8, filter=_to_store_filter(filters))
    min_score = _min_score()
    kept: list[ScoredChunk] = []
    for document, score in pairs:
        chunk = _to_chunk(document, score, base)
        if _is_relevant(chunk, float(score), query, min_score):
            kept.append(chunk)
    return kept


def chunks_to_sources(chunks: list, base: KnowledgeBase) -> list[dict]:
    sources: list[dict] = []
    for index, chunk in enumerate(chunks, start=1):
        source_id = f"S{index}"
        if isinstance(chunk, ScoredChunk):
            sources.append(
                {
                    "id": source_id,
                    "documentId": chunk.document_id,
                    "title": chunk.title,
                    "page": chunk.page,
                    "section": chunk.section,
                    "excerpt": chunk.content,
                    "knowledgeBase": chunk.knowledge_base or base.value,
                }
            )
            continue
        if isinstance(chunk, dict):
            sources.append(
                {
                    "id": source_id,
                    "documentId": chunk.get("documentId") or chunk.get("document_id") or "",
                    "title": chunk.get("title") or chunk.get("originalName") or "",
                    "page": chunk.get("page") or chunk.get("pageNumber"),
                    "section": chunk.get("section"),
                    "excerpt": chunk.get("excerpt") or chunk.get("content") or "",
                    "knowledgeBase": chunk.get("knowledgeBase") or chunk.get("knowledge_base") or base.value,
                }
            )
            continue
        metadata = getattr(chunk, "metadata", None) or {}
        content = getattr(chunk, "page_content", None) or getattr(chunk, "content", str(chunk))
        sources.append(
            {
                "id": source_id,
                "documentId": metadata.get("documentId", ""),
                "title": metadata.get("originalName") or metadata.get("title") or "",
                "page": metadata.get("pageNumber") or metadata.get("page"),
                "section": metadata.get("section"),
                "excerpt": str(content),
                "knowledgeBase": metadata.get("knowledgeBase") or base.value,
            }
        )
    return sources


def format_source_context(sources: list[dict]) -> str:
    lines = [f"[{item['id']}] {item.get('excerpt') or ''}" for item in sources]
    return "以下资料仅供回答使用，请为事实句标注对应编号：\n" + "\n".join(lines)


def _resolve_store(base: KnowledgeBase, collection: str):
    if _vector_stores is not None:
        if hasattr(_vector_stores, "for_collection"):
            return _vector_stores.for_collection(collection)
        if callable(_vector_stores):
            return _vector_stores(collection)
        raise TypeError("injected vector stores must expose for_collection(collection)")
    from app.core.config import get_settings
    from app.core.llm import create_embeddings
    from app.rag.qdrant import get_vector_store

    settings = get_settings()
    return get_vector_store(settings, base, create_embeddings(settings))


def _to_store_filter(filters: dict | None):
    if not filters:
        return None
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return Filter(
        must=[
            FieldCondition(key=key, match=MatchValue(value=value))
            for key, value in filters.items()
        ]
    )


def _min_score() -> float:
    try:
        from app.core.config import get_settings

        return float(get_settings().rag_min_score)
    except Exception:
        return 0.3


def _is_relevant(chunk: ScoredChunk, score: float, query: str, min_score: float) -> bool:
    if score >= min_score:
        return True
    return _keyword_hit(query, chunk.content)


def _keyword_hit(query: str, content: str) -> bool:
    import re

    chars = re.findall(r"[\u4e00-\u9fff]", query or "")
    text = content or ""
    return any("".join(chars[index:index + 2]) in text for index in range(len(chars) - 1))


def _to_chunk(document, score: float, base: KnowledgeBase) -> ScoredChunk:
    metadata = getattr(document, "metadata", None) or {}
    content = getattr(document, "page_content", None)
    if content is None:
        content = getattr(document, "content", str(document))
    return ScoredChunk(
        content=str(content),
        score=float(score),
        document_id=str(metadata.get("documentId") or ""),
        title=str(metadata.get("originalName") or metadata.get("title") or ""),
        page=metadata.get("pageNumber") if metadata.get("pageNumber") is not None else metadata.get("page"),
        section=metadata.get("section"),
        knowledge_base=str(metadata.get("knowledgeBase") or base.value),
        metadata=dict(metadata),
    )
