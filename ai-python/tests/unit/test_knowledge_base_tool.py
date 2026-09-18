import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain_core.documents import Document

from app.graphs.hospital.tools import knowledge_base as kb


class _Retriever:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return self.documents


def test_retrieve_returns_empty_for_blank_query(monkeypatch):
    monkeypatch.setattr(kb, "get_hospital_retriever", lambda: _Retriever([]))

    assert kb.retrieve_hospital_documents("   ") == []


def test_retrieve_swallows_backend_failure(monkeypatch):
    def boom():
        raise RuntimeError("chroma down")

    monkeypatch.setattr(kb, "get_hospital_retriever", boom)

    assert kb.retrieve_hospital_documents("感冒") == []


def test_tool_reports_miss_without_raising(monkeypatch):
    monkeypatch.setattr(kb, "get_hospital_retriever", lambda: _Retriever([]))

    assert kb.search_hospital_knowledge.invoke({"query": "感冒"}) == "（院内知识库无命中。）"


def test_tool_formats_hits(monkeypatch):
    documents = [Document(
        page_content="多休息",
        metadata={
            "source_name": "院内资料",
            "page": 1,
            "status": "active",
            "effective_from": "2025-01-01T00:00:00+00:00",
        },
    )]
    monkeypatch.setattr(kb, "get_hospital_retriever", lambda: _Retriever(documents))

    text = kb.search_hospital_knowledge.invoke({"query": "感冒"})

    assert "[S1] 来源：院内资料；版本：未标注；页码：1" in text
    assert "多休息" in text


def test_tool_name_is_stable():
    assert kb.search_hospital_knowledge.name == "search_hospital_knowledge"
