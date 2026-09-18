from datetime import UTC, datetime, timedelta
from hashlib import sha256

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.rag import chroma


class _HashEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        digest = sha256(text.encode("utf-8")).digest()
        return [byte / 255.0 for byte in digest[:8]]


def _reset_chroma(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(chroma, "hospital_collection", "test_hospital")
    chroma.get_chroma_client.cache_clear()
    chroma.get_embeddings.cache_clear()
    monkeypatch.setattr(chroma, "get_embeddings", lambda: _HashEmbeddings())


def _lifecycle_doc(
    *,
    document_id: str,
    version: int,
    status: str,
    content: str,
    now: datetime,
    expires_at: str | None = None,
) -> Document:
    return Document(
        page_content=content,
        metadata=chroma.sanitize_chroma_metadata({
            "document_id": document_id,
            "version": version,
            "status": status,
            "effective_from": (now - timedelta(days=1)).isoformat(),
            "expires_at": expires_at,
            "checksum": "abc",
            "source_name": "guide.txt",
            "uploaded_by": 1,
            "updated_at": now.isoformat(),
            "chunk_id": f"{document_id}-{version}",
            "chunk_count": 1,
        }),
    )


def test_active_document_filter_uses_flat_where_clause():
    payload = chroma.active_document_filter(datetime(2026, 9, 13, tzinfo=UTC))

    assert payload["$and"][0] == {"status": {"$eq": "active"}}
    assert "effective_from_ts" in payload["$and"][1]
    assert payload["$and"][2]["$or"][0] == {"expires_at_ts": {"$eq": 0}}
    assert "expires_at_ts" in payload["$and"][2]["$or"][1]


def test_sanitize_chroma_metadata_replaces_none_with_empty_string():
    cleaned = chroma.sanitize_chroma_metadata({
        "status": "active",
        "expires_at": None,
        "version": 2,
    })

    assert cleaned["expires_at"] == ""
    assert cleaned["expires_at_ts"] == 0
    assert cleaned["version"] == 2


def test_list_update_and_delete_document_points(tmp_path, monkeypatch):
    _reset_chroma(tmp_path, monkeypatch)
    now = datetime(2026, 9, 13, tzinfo=UTC)
    documents = [
        _lifecycle_doc(
            document_id="doc-1",
            version=1,
            status="active",
            content="旧版就诊须知",
            now=now,
        ),
        _lifecycle_doc(
            document_id="doc-1",
            version=2,
            status="active",
            content="新版就诊须知",
            now=now,
        ),
        _lifecycle_doc(
            document_id="doc-2",
            version=1,
            status="active",
            content="另一份资料",
            now=now,
        ),
    ]
    client = chroma.get_chroma_client()
    chroma.ensure_collection(client, chroma.hospital_collection)
    store = chroma.get_store(client, chroma.hospital_collection, _HashEmbeddings())
    store.add_documents(
        documents=documents,
        ids=["doc-1-v1", "doc-1-v2", "doc-2-v1"],
    )

    records = chroma.list_document_records("doc-1")
    assert [item["version"] for item in records] == [1, 2]
    assert all(item["status"] == "active" for item in records)

    chroma.set_document_status("doc-1", "superseded", version=1)
    updated = {item["version"]: item["status"] for item in chroma.list_document_records("doc-1")}
    assert updated == {1: "superseded", 2: "active"}
    assert chroma.list_document_records("doc-2")[0]["status"] == "active"

    chroma.delete_document_points("doc-1", version=1)
    remaining = chroma.list_document_records("doc-1")
    assert [item["version"] for item in remaining] == [2]
    chroma.delete_document_points("doc-1")
    assert chroma.list_document_records("doc-1") == []
    assert chroma.list_document_records("doc-2")[0]["document_id"] == "doc-2"


def test_retriever_where_filter_keeps_only_active_effective_chunks(tmp_path, monkeypatch):
    _reset_chroma(tmp_path, monkeypatch)
    now = datetime.now(UTC)
    expired = (now - timedelta(hours=1)).isoformat()
    documents = [
        _lifecycle_doc(
            document_id="keep",
            version=1,
            status="active",
            content="院内感冒护理说明",
            now=now,
        ),
        _lifecycle_doc(
            document_id="inactive",
            version=1,
            status="inactive",
            content="院内感冒护理说明",
            now=now,
        ),
        _lifecycle_doc(
            document_id="expired",
            version=1,
            status="active",
            content="院内感冒护理说明",
            now=now,
            expires_at=expired,
        ),
    ]
    client = chroma.get_chroma_client()
    chroma.ensure_collection(client, chroma.hospital_collection)
    store = chroma.get_store(client, chroma.hospital_collection, _HashEmbeddings())
    store.add_documents(documents=documents, ids=["keep", "inactive", "expired"])

    hits = chroma.get_hospital_retriever().invoke("院内感冒护理说明")

    assert [doc.metadata["document_id"] for doc in hits] == ["keep"]
