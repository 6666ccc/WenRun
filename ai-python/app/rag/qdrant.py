"""Qdrant client and vector-store factories. Never connect at import time."""

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.rag.collections import COLLECTIONS, KnowledgeBase


def get_qdrant_client(settings: Settings) -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def get_vector_store(settings: Settings, base: KnowledgeBase, embeddings) -> QdrantVectorStore:
    if not isinstance(base, KnowledgeBase):
        raise TypeError("get_vector_store accepts KnowledgeBase only")
    return QdrantVectorStore(
        client=get_qdrant_client(settings),
        collection_name=COLLECTIONS[base],
        embedding=embeddings,
    )
