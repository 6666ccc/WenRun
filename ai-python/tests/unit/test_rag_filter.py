import importlib
import sys

import pytest

from app.rag.collections import COLLECTIONS, KnowledgeBase
from app.rag.rag import retrieve


def test_medical_retrieval_never_uses_hospital_collection(fake_vector_stores):
    result = retrieve(KnowledgeBase.MEDICAL, "口腔溃疡原因")
    assert fake_vector_stores.last_collection == "wenrun_medical_general"
    assert result is not None


def test_retrieve_rejects_raw_collection_string(fake_vector_stores):
    with pytest.raises(TypeError):
        retrieve("wenrun_medical_general", "口腔溃疡原因")


class _Doc:
    def __init__(self, content, metadata=None):
        self.page_content = content
        self.metadata = metadata or {}


def test_retrieve_drops_low_relevance_chunks(fake_vector_stores):
    fake_vector_stores.pairs = [
        (_Doc("口腔溃疡注意口腔卫生", {"documentId": "a"}), 0.92),
        (_Doc("无关内容", {"documentId": "b"}), 0.05),
    ]
    result = retrieve(KnowledgeBase.MEDICAL, "口腔溃疡")
    assert [chunk.document_id for chunk in result] == ["a"]


def test_retrieve_keeps_high_score_and_keyword_matches(fake_vector_stores):
    fake_vector_stores.pairs = [
        (_Doc("口腔溃疡护理要点", {"documentId": "kw"}), 0.05),
        (_Doc("日常饮食建议", {"documentId": "hi"}), 0.91),
    ]
    result = retrieve(KnowledgeBase.MEDICAL, "口腔溃疡怎么护理")
    assert [chunk.document_id for chunk in result] == ["kw", "hi"]


def test_collection_mapping_is_isolated():
    assert COLLECTIONS[KnowledgeBase.HOSPITAL] == "wenrun_hospital_custom"
    assert COLLECTIONS[KnowledgeBase.MEDICAL] == "wenrun_medical_general"
    assert COLLECTIONS[KnowledgeBase.MEMORY] == "wenrun_conversation_memory"


def test_ingest_rejects_unsupported_extension():
    from io import BytesIO

    from app.rag.ingest import ingest_document

    with pytest.raises(ValueError):
        ingest_document(BytesIO(b"not-a-doc"), "doc-1", KnowledgeBase.MEDICAL, "notes.txt")


def test_hospital_node_numbers_only_hospital_chunks():
    from app.graphs.hospital.graph import GraphDependencies
    from app.graphs.hospital.nodes.hospital_node import build_hospital_node

    class HospitalRetriever:
        def __call__(self, query):
            return [{
                "content": "门诊八点开始挂号",
                "documentId": "doc-h",
                "title": "门诊指南",
                "knowledgeBase": "hospital-custom",
            }]

    class ReplyAgent:
        def invoke(self, payload):
            return "门诊八点开始挂号 [S1]"

    node = build_hospital_node(
        GraphDependencies(
            intent_agent=None,
            chat_agent=None,
            hospital_agent=ReplyAgent(),
            medical_agent=None,
            hospital_retriever=HospitalRetriever(),
        )
    )
    result = node({
        "messages": [{"role": "user", "content": "几点挂号"}],
        "intent": "hospital",
        "sources": [],
    })
    assert result["sources"][0]["id"] == "S1"
    assert result["sources"][0]["knowledgeBase"] == "hospital-custom"
    assert result["sources"][0]["excerpt"] == "门诊八点开始挂号"


def test_medical_node_numbers_only_medical_chunks():
    from app.graphs.hospital.graph import GraphDependencies
    from app.graphs.hospital.nodes.medical_node import build_medical_node

    class MedicalRetriever:
        def __call__(self, query):
            return [{
                "content": "口腔溃疡常见诱因包括免疫力下降",
                "documentId": "doc-m",
                "title": "口腔护理",
                "knowledgeBase": "medical-general",
            }]

    class ReplyAgent:
        def invoke(self, payload):
            return "口腔溃疡常见诱因包括免疫力下降 [S1]"

    node = build_medical_node(
        GraphDependencies(
            intent_agent=None,
            chat_agent=None,
            hospital_agent=None,
            medical_agent=ReplyAgent(),
            medical_retriever=MedicalRetriever(),
        )
    )
    result = node({
        "messages": [{"role": "user", "content": "口腔溃疡原因"}],
        "intent": "medical",
        "sources": [],
    })
    assert result["sources"][0]["id"] == "S1"
    assert result["sources"][0]["knowledgeBase"] == "medical-general"


def test_qdrant_module_does_not_connect_on_import(monkeypatch):
    def boom_client(*args, **kwargs):
        raise AssertionError("import must not construct QdrantClient")

    def boom_embeddings(*args, **kwargs):
        raise AssertionError("import must not construct embeddings")

    monkeypatch.setattr("qdrant_client.QdrantClient", boom_client)
    monkeypatch.setattr("langchain_openai.OpenAIEmbeddings", boom_embeddings)
    sys.modules.pop("app.rag.qdrant", None)
    module = importlib.import_module("app.rag.qdrant")
    assert callable(module.get_qdrant_client)
    assert callable(module.get_vector_store)
    assert not hasattr(module, "qdrantClient")
    assert not hasattr(module, "store")
    assert not hasattr(module, "embeddings")
