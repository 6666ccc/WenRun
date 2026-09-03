import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain.messages import AIMessage, HumanMessage

from app.graphs.hospital.nodes import knowledge as knowledge_mod
from app.graphs.hospital.nodes.knowledge import knowledge_node


def test_knowledge_node_skips_when_not_selected():
    assert knowledge_node({"selected_agents": ["chat"], "messages": []}) == {}


def test_knowledge_node_lets_agent_receive_raw_history(monkeypatch):
    captured: dict = {}
    history = [
        HumanMessage(content="你好，我最近心情很难受所以感冒吃什么药"),
    ]

    class FakeRetriever:
        def invoke(self, query):
            assert query == "你好，我最近心情很难受所以感冒吃什么药"
            return []

    class FakeAgent:
        def invoke(self, payload):
            captured["messages"] = payload["messages"]
            return {"messages": [HumanMessage(content="摘要 [1]")]}

    monkeypatch.setattr(knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever())
    monkeypatch.setattr(knowledge_mod, "agent", FakeAgent())

    reply = knowledge_node(
        {"selected_agents": ["knowledge"], "messages": history}
    )

    assert reply == {"knowledge_reply": "摘要 [1]", "rag_sources": []}
    assert captured["messages"] == history


def test_knowledge_node_streams_answer_when_rag_hits(monkeypatch):
    """RAG 命中时必须走 stream，SSE 路由才能逐字转发本节点的正文。"""

    from langchain_core.documents import Document

    class FakeRetriever:
        def invoke(self, query):
            return [
                Document(
                    page_content="多休息、多喝水",
                    metadata={"source_name": "院内资料", "page": 3},
                )
            ]

    class StreamOnlyModel:
        def stream(self, messages):
            for piece in ("院内资料显示，", "请多休息。"):
                yield AIMessage(content=piece)

    monkeypatch.setattr(knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever())
    monkeypatch.setattr(knowledge_mod, "model", StreamOnlyModel())

    reply = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "messages": [HumanMessage(content="感冒怎么办")],
        }
    )

    assert reply["knowledge_reply"] == "院内资料显示，请多休息。"
    assert reply["rag_sources"] == [
        {"id": "S1", "document_id": None, "title": "院内资料", "page": 3}
    ]
