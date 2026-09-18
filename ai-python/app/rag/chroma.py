import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

embedding_model = os.getenv("EMBEDDING_MODEL")
embedding_apikey = os.getenv("DASHSCOPE_API_KEY")
embedding_url = os.getenv("DASHSCOPE_BASE_URL")
hospital_collection = os.getenv("CHROMA_HOSPITAL_COLLECTION", "wenrun_hospital_custom")
RAG_METADATA_SCHEMA_VERSION = "rag-metadata-v2"
_COLLECTION_METADATA = {"hnsw:space": "cosine"}


def persist_directory() -> str:
    configured = os.getenv("CHROMA_PERSIST_DIR", "").strip()
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return str(path.resolve())
    return str(Path(__file__).resolve().parents[2] / "data" / "chroma")


@lru_cache
def get_chroma_client() -> chromadb.ClientAPI:
    path = persist_directory()
    Path(path).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=path,
        settings=Settings(anonymized_telemetry=False),
    )


def get_store(
    client: chromadb.ClientAPI,
    collection_name: str,
    embeddings: Embeddings,
) -> Chroma:
    return Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings,
        collection_metadata=_COLLECTION_METADATA,
        create_collection_if_not_exists=True,
    )


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    if not all((embedding_model, embedding_apikey, embedding_url)):
        raise RuntimeError(
            "缺少 EMBEDDING_MODEL、DASHSCOPE_API_KEY 或 DASHSCOPE_BASE_URL"
        )
    return OpenAIEmbeddings(
        model=embedding_model,
        api_key=embedding_apikey,
        base_url=embedding_url,
        # DashScope Embedding 接口单次最多处理 20 条文本；超过会返回 400。
        chunk_size=20,
        check_embedding_ctx_length=False,
    )


def ensure_collection(client: chromadb.ClientAPI, collection_name: str) -> None:
    client.get_or_create_collection(
        name=collection_name,
        metadata=_COLLECTION_METADATA,
    )


def _unix_seconds(value: object) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.astimezone(UTC).timestamp())


def sanitize_chroma_metadata(metadata: dict) -> dict[str, str | int | float | bool]:
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            cleaned[key] = ""
        elif isinstance(value, (bool, int, float, str)):
            cleaned[key] = value
        else:
            cleaned[key] = str(value)
    if "effective_from" in metadata:
        cleaned["effective_from_ts"] = _unix_seconds(metadata.get("effective_from"))
    if "expires_at" in metadata:
        cleaned["expires_at_ts"] = _unix_seconds(metadata.get("expires_at"))
    return cleaned


def active_document_filter(now: datetime | None = None) -> dict:
    """Chroma-side lifecycle filter; safety.py repeats the check after retrieval.

    Chroma 1.5 `$lte`/`$gt` only accept numbers, so range checks use epoch seconds
    written by ``sanitize_chroma_metadata``. Missing expiry is stored as 0.
    """

    current = int((now or datetime.now(UTC)).astimezone(UTC).timestamp())
    return {
        "$and": [
            {"status": {"$eq": "active"}},
            {"effective_from_ts": {"$lte": current}},
            {"$or": [
                {"expires_at_ts": {"$eq": 0}},
                {"expires_at_ts": {"$gt": current}},
            ]},
        ]
    }


def document_filter(
    document_id: str, *, version: int | None = None, checksum: str | None = None
) -> dict:
    conditions: list[dict] = [{"document_id": {"$eq": document_id}}]
    if version is not None:
        conditions.append({"version": {"$eq": version}})
    if checksum is not None:
        conditions.append({"checksum": {"$eq": checksum}})
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _hospital_collection():
    client = get_chroma_client()
    ensure_collection(client, hospital_collection)
    return client.get_collection(hospital_collection)


def list_document_records(document_id: str) -> list[dict]:
    """Read one representative metadata record for every indexed version."""

    collection = _hospital_collection()
    records: dict[int, dict] = {}
    offset = 0
    batch = 256
    while True:
        result = collection.get(
            where=document_filter(document_id),
            include=["metadatas"],
            limit=batch,
            offset=offset,
        )
        ids = result.get("ids") or []
        for metadata in result.get("metadatas") or []:
            if not isinstance(metadata, dict):
                continue
            version = metadata.get("version")
            if isinstance(version, float) and version.is_integer():
                version = int(version)
            if isinstance(version, int):
                records.setdefault(version, dict(metadata))
        if len(ids) < batch:
            break
        offset += batch
    return [records[key] for key in sorted(records)]


def set_document_status(
    document_id: str,
    status: str,
    *,
    version: int | None = None,
    updated_at: str | None = None,
) -> None:
    collection = _hospital_collection()
    result = collection.get(
        where=document_filter(document_id, version=version),
        include=["metadatas"],
    )
    ids = result.get("ids") or []
    if not ids:
        return
    stamp = updated_at or datetime.now(UTC).isoformat()
    metadatas = []
    for metadata in result.get("metadatas") or []:
        item = dict(metadata or {})
        item["status"] = status
        item["updated_at"] = stamp
        metadatas.append(sanitize_chroma_metadata(item))
    collection.update(ids=ids, metadatas=metadatas)


def delete_document_points(document_id: str, *, version: int | None = None) -> None:
    _hospital_collection().delete(
        where=document_filter(document_id, version=version)
    )


def get_hospital_retriever():
    client = get_chroma_client()
    embeddings = get_embeddings()
    ensure_collection(client, hospital_collection)
    store = get_store(client, hospital_collection, embeddings)
    return store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": 5,
            "score_threshold": 0.8,
            "filter": active_document_filter(),
        },
    )
