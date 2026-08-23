import os
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


@lru_cache
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
        },
    )
