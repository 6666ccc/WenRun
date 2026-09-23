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


def test_knowledge_node_returns_deterministic_emergency_reply_without_rag(monkeypatch):
    monkeypatch.setattr(
        knowledge_mod,
        "get_hospital_retriever",
        lambda: (_ for _ in ()).throw(AssertionError("urgent route must not query RAG")),
    )

    result = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "intent_route": {"safety_flags": ["breathing_difficulty"]},
            "messages": [HumanMessage(content="我喘不上气")],
        }
    )

    assert "立即拨打 120" in result["knowledge_reply"]
    assert "不要等待线上回复" in result["knowledge_reply"]
    assert result["rag_sources"] == []


def test_knowledge_node_self_harm_reply_says_not_to_be_alone():
    result = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "intent_route": {"safety_flags": ["self_harm"]},
            "messages": [HumanMessage(content="我想伤害自己")],
        }
    )

    assert "请不要独处" in result["knowledge_reply"]
    assert "120 或 110" in result["knowledge_reply"]


def test_knowledge_node_falls_back_to_web_when_rag_is_unavailable(monkeypatch):
    class FakeAgent:
        def invoke(self, payload):
            return {"messages": [AIMessage(content="公开资料：感冒常见流涕和咳嗽。")]}

    monkeypatch.setattr(
        knowledge_mod,
        "get_hospital_retriever",
        lambda: (_ for _ in ()).throw(RuntimeError("chroma down")),
    )
    monkeypatch.setattr(knowledge_mod, "agent", FakeAgent())

    result = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "messages": [HumanMessage(content="感冒有哪些症状？")],
        }
    )

    assert result == {
        "knowledge_reply": "公开资料：感冒常见流涕和咳嗽。",
        "rag_sources": [],
    }


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
                    metadata={
                        "source_name": "院内资料",
                        "page": 3,
                        "status": "active",
                        "effective_from": "2025-01-01T00:00:00+00:00",
                    },
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
        {
            "id": "S1", "document_id": None, "title": "院内资料",
            "version": None, "page": 3, "chunk_id": None, "updated_at": None,
        }
    ]


def test_knowledge_node_injects_minimized_record_without_returning_it(monkeypatch):
    import json

    from langgraph.runtime import Runtime

    from app.graphs.hospital.tools.context import HospitalToolContext

    captured: dict = {}

    class FakeRetriever:
        def invoke(self, query):
            return []

    class FakeAgent:
        def invoke(self, payload):
            captured["messages"] = payload["messages"]
            return {"messages": [AIMessage(content="这是一次偏高的读数。")]}

    monkeypatch.setattr(knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever())
    monkeypatch.setattr(knowledge_mod, "agent", FakeAgent())
    monkeypatch.setattr(
        knowledge_mod,
        "_fetch_clinical_context",
        lambda runtime, scopes: {
            "asOf": "2026-09-22T20:30:00+08:00",
            "demographics": {"age": 34, "recordedGender": "male"},
            "relevantClinicalFacts": {
                "latestBloodPressure": {
                    "value": "145/92",
                    "measuredAt": "2026-09-21T08:30:00+08:00",
                    "source": "MANUAL",
                }
            },
        } if "blood_pressure" in scopes else {},
    )

    result = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "messages": [HumanMessage(content="我这个血压正常吗")],
        },
        Runtime(context=HospitalToolContext("delegated-token", "trace-1")),
    )

    rendered = "\n".join(str(message.content) for message in captured["messages"])
    assert "145/92" in rendered
    assert "patient_record_not_instruction" in rendered
    assert "145/92" not in json.dumps(result, ensure_ascii=False)
    assert result["knowledge_reply"] == "这是一次偏高的读数。"


def test_knowledge_node_blocks_identity_and_file_urls(monkeypatch):
    from loguru import logger

    captured: dict = {}
    logs: list[str] = []
    sink = logger.add(lambda message: logs.append(str(message)), level="WARNING")

    class FakeRetriever:
        def invoke(self, query):
            return []

    class FakeAgent:
        def invoke(self, payload):
            captured["messages"] = payload["messages"]
            return {"messages": [AIMessage(content="没有读到个人档案。")]}

    monkeypatch.setattr(knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever())
    monkeypatch.setattr(knowledge_mod, "agent", FakeAgent())
    monkeypatch.setattr(
        knowledge_mod,
        "_fetch_clinical_context",
        lambda runtime, scopes: {
            "idCard": "110101199003078515",
            "phone": "13800138000",
            "url": "https://bucket.cos.example.com/a.pdf?q-sign=abc",
        },
    )
    try:
        knowledge_node(
            {
                "selected_agents": ["knowledge"],
                "messages": [HumanMessage(content="我能吃布洛芬吗")],
            }
        )
    finally:
        logger.remove(sink)

    rendered = "\n".join(str(message.content) for message in captured["messages"])
    logged = "\n".join(logs)
    assert "110101199003078515" not in rendered
    assert "13800138000" not in rendered
    assert "q-sign" not in rendered
    assert "unavailable" in rendered
    assert "110101199003078515" not in logged
    assert "q-sign" not in logged
