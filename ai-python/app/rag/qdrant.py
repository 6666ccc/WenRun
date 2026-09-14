import os
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

# 步骤一：加载 AI 服务自己的 .env，避免依赖当前命令行工作目录。
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

qdrant_url = os.getenv("QDRANT_URL")
embedding_model = os.getenv("EMBEDDING_MODEL")
embedding_apikey = os.getenv("DASHSCOPE_API_KEY")
embedding_url = os.getenv("DASHSCOPE_BASE_URL")
hospital_collection = os.getenv("QDRANT_HOSPITAL_COLLECTION", "wenrun_hospital_custom")
RAG_METADATA_SCHEMA_VERSION = "rag-metadata-v2"


# 步骤二：创建并缓存 Qdrant 客户端。
@lru_cache
def get_qdrant_client() -> QdrantClient:
    if not qdrant_url:
        raise RuntimeError("缺少 QDRANT_URL，无法连接 Qdrant")
    return QdrantClient(url=qdrant_url, api_key=None, timeout=10)


# 步骤三：将 Qdrant client 包装为 LangChain 的 VectorStore。
def get_store(
    client: QdrantClient,
    collection_name: str,
    embeddings: Embeddings,
) -> QdrantVectorStore:
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        content_payload_key="page_content",
        metadata_payload_key="metadata",
    )


# 步骤四：创建并缓存 embedding 模型；入库和检索必须使用同一模型。
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


# 步骤五：首次使用时创建 collection，向量维度由 embedding 模型实际输出决定。
def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        ),
    )


def active_document_filter(now: datetime | None = None) -> models.Filter:
    """Qdrant-side lifecycle filter; safety.py repeats the check after retrieval."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    return models.Filter(must=[
        models.FieldCondition(
            key="metadata.status", match=models.MatchValue(value="active")
        ),
        models.FieldCondition(
            key="metadata.effective_from",
            range=models.DatetimeRange(lte=current),
        ),
        models.Filter(should=[
            models.IsNullCondition(
                is_null=models.PayloadField(key="metadata.expires_at")
            ),
            models.FieldCondition(
                key="metadata.expires_at",
                range=models.DatetimeRange(gt=current),
            ),
        ]),
    ])


def document_filter(
    document_id: str, *, version: int | None = None, checksum: str | None = None
) -> models.Filter:
    conditions: list[models.Condition] = [
        models.FieldCondition(
            key="metadata.document_id", match=models.MatchValue(value=document_id)
        )
    ]
    if version is not None:
        conditions.append(models.FieldCondition(
            key="metadata.version", match=models.MatchValue(value=version)
        ))
    if checksum is not None:
        conditions.append(models.FieldCondition(
            key="metadata.checksum", match=models.MatchValue(value=checksum)
        ))
    return models.Filter(must=conditions)


def list_document_records(document_id: str) -> list[dict]:
    """Read one representative metadata record for every indexed version."""

    client = get_qdrant_client()
    records: dict[int, dict] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=hospital_collection,
            scroll_filter=document_filter(document_id),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = getattr(point, "payload", None) or {}
            metadata = payload.get("metadata") if isinstance(payload, dict) else None
            if not isinstance(metadata, dict):
                continue
            version = metadata.get("version")
            if isinstance(version, int):
                records.setdefault(version, dict(metadata))
        if offset is None:
            break
    return [records[key] for key in sorted(records)]


def set_document_status(
    document_id: str,
    status: str,
    *,
    version: int | None = None,
    updated_at: str | None = None,
) -> None:
    client = get_qdrant_client()
    client.set_payload(
        collection_name=hospital_collection,
        payload={
            "status": status,
            "updated_at": updated_at or datetime.now(UTC).isoformat(),
        },
        key="metadata",
        points=models.FilterSelector(filter=document_filter(document_id, version=version)),
        wait=True,
    )


def delete_document_points(document_id: str, *, version: int | None = None) -> None:
    get_qdrant_client().delete(
        collection_name=hospital_collection,
        points_selector=models.FilterSelector(
            filter=document_filter(document_id, version=version)
        ),
        wait=True,
    )


def get_hospital_retriever():
    client = get_qdrant_client()
    embeddings = get_embeddings()

    ##步骤六判断向量数据库是否有对应的架构，没有自动创建
    if not client.collection_exists(hospital_collection):
        vector_size = len(embeddings.embed_query("dimension probe"))
        ensure_collection(client, hospital_collection, vector_size)

    ##获取向量store实例
    store = get_store(client, hospital_collection, embeddings)

    return store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": 5,
            "score_threshold": 0.8,
            "filter": active_document_filter(),
        },
    )
