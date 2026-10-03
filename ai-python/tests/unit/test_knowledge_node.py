import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain.messages import AIMessage, AIMessageChunk, HumanMessage

from app.graphs.hospital.nodes import knowledge as knowledge_mod
from app.graphs.hospital.nodes.knowledge import knowledge_node


def test_knowledge_node_skips_when_not_selected():
    assert knowledge_node({"selected_agents": ["chat"], "messages": []}) == {}


def test_knowledge_node_returns_deterministic_emergency_reply_without_rag(monkeypatch):
    monkeypatch.setattr(
        knowledge_mod,
        "get_hospital_retriever",
        lambda: (_ for _ in ()).throw(
            AssertionError("urgent route must not query RAG")
        ),
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
        def invoke(self, payload, *, context):
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
        def invoke(self, payload, *, context):
            captured["messages"] = payload["messages"]
            return {"messages": [HumanMessage(content="摘要 [1]")]}

    monkeypatch.setattr(
        knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever()
    )
    monkeypatch.setattr(knowledge_mod, "agent", FakeAgent())

    reply = knowledge_node({"selected_agents": ["knowledge"], "messages": history})

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
        def bind_tools(self, tools):
            assert [item.name for item in tools] == ["get_my_clinical_context"]
            return self

        def stream(self, messages):
            for piece in ("院内资料显示，", "请多休息。"):
                yield AIMessageChunk(content=piece)

    monkeypatch.setattr(
        knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever()
    )
    monkeypatch.setattr(knowledge_mod, "model", StreamOnlyModel())

    reply = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "messages": [HumanMessage(content="感冒怎么办")],
        }
    )

    assert reply["knowledge_reply"] == "院内资料显示，请多休息。"
    assert [
        {
            key: source[key]
            for key in (
                "id",
                "document_id",
                "title",
                "version",
                "page",
                "chunk_id",
                "updated_at",
            )
        }
        for source in reply["rag_sources"]
    ] == [
        {
            "id": "S1",
            "document_id": None,
            "title": "院内资料",
            "version": None,
            "page": 3,
            "chunk_id": None,
            "updated_at": None,
        }
    ]


def test_knowledge_node_reads_record_only_after_a_model_tool_call(monkeypatch):
    from langchain_core.documents import Document
    from langgraph.runtime import Runtime

    from app.graphs.hospital.tools.context import HospitalToolContext

    class FakeRetriever:
        def invoke(self, query):
            return [
                Document(
                    page_content="血压知识",
                    metadata={
                        "source_name": "院内资料",
                        "status": "active",
                        "effective_from": "2025-01-01T00:00:00+00:00",
                    },
                )
            ]

    class ScriptedModel:
        def __init__(self, turns):
            self.turns = list(turns)
            self.seen = []

        def bind_tools(self, tools):
            assert [item.name for item in tools] == ["get_my_clinical_context"]
            return self

        def stream(self, messages):
            self.seen.append(list(messages))
            yield from self.turns.pop(0)

    calls = []

    def fake_read(scopes, context):
        calls.append((scopes, context.delegated_token))
        return '【patient_clinical_context】{"value":"145/92"}'

    monkeypatch.setattr(
        knowledge_mod, "get_hospital_retriever", lambda: FakeRetriever()
    )
    monkeypatch.setattr(knowledge_mod, "read_my_clinical_context", fake_read)

    for question in ("人的正常血压是多少", "我的胸有点闷，帮我查一下正常血压是多少"):
        scripted = ScriptedModel([[AIMessageChunk(content="正常血压的通用说明。")]])
        monkeypatch.setattr(knowledge_mod, "model", scripted)
        result = knowledge_node(
            {
                "selected_agents": ["knowledge"],
                "messages": [HumanMessage(content=question)],
            }
        )
        assert result["knowledge_reply"] == "正常血压的通用说明。"
        assert len(scripted.seen) == 1
    assert calls == []

    scripted = ScriptedModel(
        [
            [
                AIMessageChunk(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_my_clinical_context",
                            "args": {"scopes": ["blood_pressure"]},
                            "id": "call-1",
                            "type": "tool_call",
                        }
                    ],
                )
            ],
            [AIMessageChunk(content="这次读数需要结合测量时间看。")],
        ]
    )
    monkeypatch.setattr(knowledge_mod, "model", scripted)
    result = knowledge_node(
        {
            "selected_agents": ["knowledge"],
            "messages": [HumanMessage(content="俺上次的血压是多少")],
        },
        Runtime(context=HospitalToolContext("delegated-token", "trace-1")),
    )

    assert calls == [(["blood_pressure"], "delegated-token")]
    assert "145/92" in str(scripted.seen[1][-1].content)
    assert "145/92" not in str(result)
    assert result["knowledge_reply"] == "这次读数需要结合测量时间看。"
