import json

from fastapi.testclient import TestClient
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.api.routes import chat as chat_route
from app.core.config import get_settings
from app.main import create_app


def _sse_events(response):
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_health_endpoint_reports_service_liveness():
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_stream_uses_frontend_sse_contract(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    captured: dict = {}

    class FakeGraph:
        def invoke(self, state):
            captured["state"] = state
            return {
                "final_reply": "已生成回复",
                "selected_agents": ["knowledge"],
                "rag_sources": [{"id": "S1", "title": "院内资料", "page": 1}],
            }

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers={"X-Api-Key": "test-key"},
        json={
            "message": "感冒怎么办",
            "conversationId": "demo",
            "userContext": {"patientId": 12},
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(response)
    assert [event["type"] for event in events] == [
        "status", "status", "citation", "token", "done"
    ]
    assert events[-1]["conversationId"] == "demo"
    assert events[-1]["reply"] == "已生成回复"
    assert captured["state"]["conversation_id"] == "demo"
    assert captured["state"]["patient_id"] == 12
    assert isinstance(captured["state"]["messages"][0], HumanMessage)
    assert captured["state"]["messages"][0].content == "感冒怎么办"


def test_chat_stream_forwards_visible_graph_message_chunks(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    captured: dict = {}

    class FakeGraph:
        async def astream(self, state, *, stream_mode, subgraphs, version):
            captured["state"] = state
            captured["stream_mode"] = stream_mode
            captured["subgraphs"] = subgraphs
            captured["version"] = version
            yield {
                "type": "values",
                "data": {"selected_agents": ["chat"]},
            }
            # Routing output must never reach the browser.
            yield {
                "type": "messages",
                "data": (
                    AIMessageChunk(content='{"selected_agents":["chat"]}'),
                    {"langgraph_node": "begin_node"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    AIMessageChunk(content="你好"),
                    {"langgraph_node": "chat_node"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    AIMessageChunk(content="，有什么可以帮您？"),
                    {"langgraph_node": "model"},
                ),
                "ns": ("chat_node:run-1", "model:run-2"),
            }
            yield {
                "type": "values",
                "data": {
                    "final_reply": "你好，有什么可以帮您？",
                    "selected_agents": ["chat"],
                    "rag_sources": [],
                },
            }

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers={"X-Api-Key": "test-key"},
        json={
            "message": "你好",
            "conversationId": "stream-demo",
        },
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert [event["type"] for event in events] == [
        "status", "token", "token", "done"
    ]
    assert [event["content"] for event in events if event["type"] == "token"] == [
        "你好", "，有什么可以帮您？"
    ]
    assert events[-1]["reply"] == "你好，有什么可以帮您？"
    assert captured["stream_mode"] == ["messages", "values"]
    assert captured["subgraphs"] is True
    assert captured["version"] == "v2"


def test_chat_stream_hides_knowledge_internals_and_only_exposes_final_reply(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    class FakeGraph:
        async def astream(self, state, *, stream_mode, subgraphs, version):
            yield {
                "type": "values",
                "data": {"selected_agents": ["knowledge"]},
            }
            # Tool output must never be sent as patient-facing text.
            yield {
                "type": "messages",
                "data": (
                    ToolMessage(content="RAW_SEARCH_RESULT", tool_call_id="call-1"),
                    {"langgraph_node": "tools"},
                ),
                "ns": ("knowledge_node:run-1", "tools:run-2"),
            }
            # Knowledge-agent model output is also internal until final_node.
            yield {
                "type": "messages",
                "data": (
                    AIMessageChunk(content="内部检索摘要"),
                    {"langgraph_node": "model"},
                ),
                "ns": ("knowledge_node:run-1", "model:run-3"),
            }
            # Even under final_node, non-assistant messages and tool calls stay hidden.
            yield {
                "type": "messages",
                "data": (
                    SystemMessage(content="系统上下文"),
                    {"langgraph_node": "final_node"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    HumanMessage(content="用户上下文"),
                    {"langgraph_node": "final_node"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    AIMessage(
                        content="工具调用参数",
                        tool_calls=[
                            {
                                "name": "web_search",
                                "args": {"query": "感冒"},
                                "id": "call-2",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    {"langgraph_node": "final_node"},
                ),
            }
            yield {
                "type": "messages",
                "data": (
                    AIMessage(content="最终面向患者的答案"),
                    {"langgraph_node": "final_node"},
                ),
            }
            yield {
                "type": "values",
                "data": {
                    "selected_agents": ["knowledge"],
                    "final_reply": "最终面向患者的答案",
                    "rag_sources": [],
                },
            }

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers={"X-Api-Key": "test-key"},
        json={
            "message": "感冒吃什么药",
            "conversationId": "knowledge-stream-demo",
        },
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert [event["type"] for event in events] == [
        "status",
        "status",
        "status",
        "token",
        "done",
    ]
    assert [event["content"] for event in events if event["type"] == "token"] == [
        "最终面向患者的答案"
    ]
    assert "RAW_SEARCH_RESULT" not in response.text
    assert "内部检索摘要" not in response.text
    assert events[-1]["reply"] == "最终面向患者的答案"


def test_stream_visible_nodes_only_streams_chat_when_chat_is_the_sole_agent():
    assert chat_route._stream_visible_nodes(["chat"]) == {"chat_node"}
    assert chat_route._stream_visible_nodes(["knowledge"]) == {"final_node"}
    assert chat_route._stream_visible_nodes(["knowledge", "chat"]) == {"final_node"}
