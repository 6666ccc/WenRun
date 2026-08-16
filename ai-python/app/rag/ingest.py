from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from langchain_core.documents import Document

from app.models.knowledge import IngestResponse
from app.rag.collections import COLLECTIONS, KnowledgeBase

ALLOWED_SUFFIXES = {".pdf", ".docx"}
_CHUNK_SIZE = 800


def ingest_document(file, document_id: str, base: KnowledgeBase, original_name: str) -> IngestResponse:
    if not isinstance(base, KnowledgeBase):
        raise TypeError("ingest_document accepts KnowledgeBase only")
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("only .pdf and .docx are supported")

    data = _read_bytes(file)
    units = _parse_pdf(data) if suffix == ".pdf" else _parse_docx(data)
    chunks = _split_units(units)
    if not chunks:
        raise ValueError("no text extracted from document")

    version = str(uuid4())
    ingested_at = datetime.now(timezone.utc).isoformat()
    documents = [
        Document(
            page_content=chunk["content"],
            metadata={
                "documentId": document_id,
                "knowledgeBase": base.value,
                "originalName": original_name,
                "pageNumber": chunk.get("pageNumber"),
                "section": chunk.get("section"),
                "chunkIndex": index,
                "documentVersion": version,
                "ingestedAt": ingested_at,
                "active": False,
            },
        )
        for index, chunk in enumerate(chunks)
    ]

    backend = _ingest_backend(base)
    try:
        backend.add_documents(documents)
        backend.activate(document_id, version)
    except Exception:
        backend.rollback(document_id, version)
        raise

    return IngestResponse(
        document_id=document_id,
        knowledge_base=base.value,
        chunk_count=len(documents),
    )


def delete_document(base: KnowledgeBase, document_id: str) -> None:
    if not isinstance(base, KnowledgeBase):
        raise TypeError("delete_document accepts KnowledgeBase only")
    _ingest_backend(base).delete_document(document_id)


def _ingest_backend(base: KnowledgeBase):
    from app.rag.rag import get_injected_vector_stores

    injected = get_injected_vector_stores()
    if injected is not None:
        collection = COLLECTIONS[base]
        store = injected.for_collection(collection) if hasattr(injected, "for_collection") else injected
        return InjectedIngestBackend(store)

    from app.core.config import get_settings
    from app.core.llm import create_embeddings
    from app.rag.qdrant import get_qdrant_client, get_vector_store

    settings = get_settings()
    embeddings = create_embeddings(settings)
    client = get_qdrant_client(settings)
    store = get_vector_store(settings, base, embeddings)
    return QdrantIngestBackend(client, store, COLLECTIONS[base], embeddings)


class InjectedIngestBackend:
    def __init__(self, store):
        self.store = store

    def add_documents(self, documents):
        adder = getattr(self.store, "add_documents", None)
        if callable(adder):
            adder(documents)
            return
        written = getattr(self.store, "documents", None)
        if written is None:
            self.store.documents = []
        self.store.documents.extend(documents)

    def activate(self, document_id: str, version: str):
        activator = getattr(self.store, "activate", None)
        if callable(activator):
            activator(document_id, version)
            return
        documents = list(getattr(self.store, "documents", []) or [])
        kept = []
        for document in documents:
            metadata = getattr(document, "metadata", {}) or {}
            if metadata.get("documentId") != document_id:
                kept.append(document)
                continue
            if metadata.get("documentVersion") == version:
                metadata["active"] = True
                kept.append(document)
        self.store.documents = kept

    def rollback(self, document_id: str, version: str):
        rollback = getattr(self.store, "rollback", None)
        if callable(rollback):
            rollback(document_id, version)
            return
        documents = list(getattr(self.store, "documents", []) or [])
        self.store.documents = [
            document
            for document in documents
            if not (
                (getattr(document, "metadata", {}) or {}).get("documentId") == document_id
                and (getattr(document, "metadata", {}) or {}).get("documentVersion") == version
            )
        ]

    def delete_document(self, document_id: str):
        deleter = getattr(self.store, "delete_document", None)
        if callable(deleter):
            deleter(document_id)
            return
        documents = list(getattr(self.store, "documents", []) or [])
        self.store.documents = [
            document
            for document in documents
            if (getattr(document, "metadata", {}) or {}).get("documentId") != document_id
        ]


class QdrantIngestBackend:
    def __init__(self, client, store, collection: str, embeddings):
        self.client = client
        self.store = store
        self.collection = collection
        self.embeddings = embeddings

    def add_documents(self, documents):
        self._ensure_collection()
        self.store.add_documents(documents)

    def activate(self, document_id: str, version: str):
        self._delete_filtered(
            must=[{"key": "documentId", "value": document_id}],
            must_not=[{"key": "documentVersion", "value": version}],
        )
        point_ids = self._scroll_ids(
            must=[
                {"key": "documentId", "value": document_id},
                {"key": "documentVersion", "value": version},
            ]
        )
        if point_ids:
            self.client.set_payload(
                collection_name=self.collection,
                payload={"active": True},
                points=point_ids,
            )

    def rollback(self, document_id: str, version: str):
        self._delete_filtered(
            must=[
                {"key": "documentId", "value": document_id},
                {"key": "documentVersion", "value": version},
            ]
        )

    def delete_document(self, document_id: str):
        try:
            self._delete_filtered(must=[{"key": "documentId", "value": document_id}])
        except Exception as exc:
            if _is_missing_collection(exc):
                return
            raise

    def _ensure_collection(self):
        if self.client.collection_exists(self.collection):
            return
        from qdrant_client.models import Distance, VectorParams

        probe = self.embeddings.embed_query("dimension-probe")
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=len(probe), distance=Distance.COSINE),
        )

    def _delete_filtered(self, must, must_not=None):
        from qdrant_client.models import FilterSelector

        self.client.delete(
            collection_name=self.collection,
            points_selector=FilterSelector(filter=_payload_filter(must, must_not)),
        )

    def _scroll_ids(self, must):
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=_payload_filter(must),
            limit=10_000,
            with_payload=False,
            with_vectors=False,
        )
        return [point.id for point in points]


def _payload_filter(must, must_not=None):
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    return Filter(
        must=[FieldCondition(key=item["key"], match=MatchValue(value=item["value"])) for item in must],
        must_not=[
            FieldCondition(key=item["key"], match=MatchValue(value=item["value"]))
            for item in (must_not or [])
        ]
        or None,
    )


def _is_missing_collection(exc: Exception) -> bool:
    text = str(exc).lower()
    return "not found" in text or "doesn't exist" in text or "does not exist" in text


def _read_bytes(file) -> bytes:
    if isinstance(file, (bytes, bytearray)):
        return bytes(file)
    read = getattr(file, "read", None)
    if not callable(read):
        raise TypeError("file must be bytes or a binary stream")
    data = read()
    seek = getattr(file, "seek", None)
    if callable(seek):
        try:
            seek(0)
        except Exception:
            pass
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def _parse_pdf(data: bytes) -> list[dict]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    units = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            units.append({"content": text, "pageNumber": index, "section": None})
    return units


def _parse_docx(data: bytes) -> list[dict]:
    from docx import Document as DocxDocument

    document = DocxDocument(BytesIO(data))
    units = []
    current_section = None
    paragraph_index = 0
    for paragraph in document.paragraphs:
        text = (paragraph.text or "").strip()
        if not text:
            continue
        style_name = ""
        if paragraph.style is not None:
            style_name = paragraph.style.name or ""
        if style_name.startswith("Heading"):
            current_section = text
            continue
        paragraph_index += 1
        units.append({
            "content": text,
            "pageNumber": None,
            "section": current_section or f"paragraph-{paragraph_index}",
        })
    return units


def _split_units(units: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    for unit in units:
        text = (unit.get("content") or "").strip()
        if not text:
            continue
        if len(text) <= _CHUNK_SIZE:
            chunks.append({**unit, "content": text})
            continue
        for start in range(0, len(text), _CHUNK_SIZE):
            part = text[start:start + _CHUNK_SIZE].strip()
            if part:
                chunks.append({**unit, "content": part})
    return chunks

