import json
from base64 import b64encode
from datetime import datetime, timedelta, timezone

import jwt
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


def _chat_auth_headers(monkeypatch) -> dict[str, str]:
    signing_key = b"a" * 32
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    monkeypatch.setenv("AI_DELEGATION_SIGNING_SECRET", b64encode(signing_key).decode())
    get_settings.cache_clear()
    now = datetime.now(timezone.utc)
    delegated_token = jwt.encode(
        {
            "iss": "wenrun-java",
            "sub": "1",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        signing_key,
        algorithm="HS256",
    )
    return {
        "X-Api-Key": "test-key",
        "X-Delegated-Token": delegated_token,
    }


def test_health_endpoint_reports_service_liveness():
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_knowledge_document_writes_file_to_rag(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    captured: dict = {}

    def fake_ingest_file(content, filename):
        captured["content"] = content
        captured["filename"] = filename
        return {
            "document_id": "doc-123",
            "filename": filename,
            "chunk_count": 3,
        }

    monkeypatch.setattr(chat_route, "ingest_file", fake_ingest_file)
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/documents",
        headers={"X-Api-Key": "test-key"},
        files={"file": ("hospital-guide.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "document_id": "doc-123",
        "filename": "hospital-guide.pdf",
        "chunk_count": 3,
    }
    assert captured == {
        "content": b"%PDF-1.7",
        "filename": "hospital-guide.pdf",
    }


def test_upload_knowledge_document_returns_bad_request_for_invalid_file(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    def fake_ingest_file(content, filename):
        raise ValueError("不支持的文件格式：.exe")

    monkeypatch.setattr(chat_route, "ingest_file", fake_ingest_file)
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/documents",
        headers={"X-Api-Key": "test-key"},
        files={"file": ("untrusted.exe", b"not a document", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "不支持的文件格式：.exe"}


def test_chat_stream_returns_500_when_delegation_secret_missing(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    monkeypatch.setenv("AI_DELEGATION_SIGNING_SECRET", "")
    monkeypatch.setenv("AI_DELEGATION_VERIFYING_SECRET", "")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers={"X-Api-Key": "test-key", "X-Delegated-Token": "any-token"},
        json={"message": "你好", "conversationId": "c1"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "delegation token verification is unavailable"}


def test_chat_stream_uses_frontend_sse_contract(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)

    captured: dict = {}

    class FakeGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["state"] = state
            captured["context"] = context
            yield {
                "type": "values",
                "data": {
                    "final_reply": "已生成回复",
                    "selected_agents": ["knowledge"],
                    "rag_sources": [{"id": "S1", "title": "院内资料", "page": 1}],
                },
            }

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
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
    assert captured["context"].delegated_token
    assert "delegated_token" not in captured["state"]


def test_chat_stream_forwards_visible_graph_message_chunks(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)

    captured: dict = {}

    class FakeGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["state"] = state
            captured["stream_mode"] = stream_mode
            captured["subgraphs"] = subgraphs
            captured["version"] = version
            yield {
                "type": "values",
                "data": {"selected_agents": ["chat"]},
            }
            # 路由输出绝不能发送到浏览器。
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
        headers=headers,
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
    headers = _chat_auth_headers(monkeypatch)

    class FakeGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {
                "type": "values",
                "data": {"selected_agents": ["knowledge"]},
            }
            # 工具输出绝不能作为面向患者的文本发送。
            yield {
                "type": "messages",
                "data": (
                    ToolMessage(content="RAW_SEARCH_RESULT", tool_call_id="call-1"),
                    {"langgraph_node": "tools"},
                ),
                "ns": ("knowledge_node:run-1", "tools:run-2"),
            }
            # 在 final_node 之前，知识 Agent 的模型输出同样属于内部内容。
            yield {
                "type": "messages",
                "data": (
                    AIMessageChunk(content="内部检索摘要"),
                    {"langgraph_node": "model"},
                ),
                "ns": ("knowledge_node:run-1", "model:run-3"),
            }
            # 即使在 final_node 下，非助手消息和工具调用也必须保持隐藏。
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
        headers=headers,
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


def test_graph_config_uses_conversation_id_as_thread_id():
    from app.models.chat import ChatRequest

    request = ChatRequest(message="你好", conversationId="conv-42")

    assert chat_route._graph_config(request) == {
        "configurable": {"thread_id": "conv-42"}
    }


def test_chat_stream_prefers_memory_graph(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    from app.graphs.hospital import checkpointing

    captured: dict = {}

    class MemoryGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["config"] = config
            yield {"type": "values", "data": {"final_reply": "记忆图回复"}}

    class StatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["used_stateless"] = True
            yield {"type": "values", "data": {"final_reply": "无记忆回复"}}

    monkeypatch.setattr(chat_route, "graph", StatelessGraph())
    checkpointing.set_memory_graph(MemoryGraph())
    try:
        client = TestClient(create_app())
        response = client.post(
            "/v1/chat/stream",
            headers=headers,
            json={"message": "你好", "conversationId": "conv-42"},
        )
    finally:
        checkpointing.set_memory_graph(None)

    assert response.status_code == 200
    assert _sse_events(response)[-1]["reply"] == "记忆图回复"
    assert captured["config"] == {"configurable": {"thread_id": "conv-42"}}
    assert "used_stateless" not in captured


def test_chat_stream_falls_back_to_stateless_graph_when_memory_disabled(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    from app.graphs.hospital import checkpointing

    class MemoryGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            raise AssertionError("memoryEnabled=false 时不得使用记忆图")
            yield  # pragma: no cover

    class StatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {"type": "values", "data": {"final_reply": "无记忆回复"}}

    monkeypatch.setattr(chat_route, "graph", StatelessGraph())
    checkpointing.set_memory_graph(MemoryGraph())
    try:
        client = TestClient(create_app())
        response = client.post(
            "/v1/chat/stream",
            headers=headers,
            json={
                "message": "你好",
                "conversationId": "conv-42",
                "memoryEnabled": False,
            },
        )
    finally:
        checkpointing.set_memory_graph(None)

    assert _sse_events(response)[-1]["reply"] == "无记忆回复"


def test_delete_conversation_memory_purges_thread(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    deleted: list[str] = []

    class FakeCheckpointer:
        async def adelete_thread(self, thread_id):
            deleted.append(thread_id)

    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: FakeCheckpointer())
    client = TestClient(create_app())
    response = client.delete(
        "/v1/chat/memory/conv-42", headers={"X-Api-Key": "test-key"}
    )

    assert response.status_code == 204
    assert deleted == ["conv-42"]


def test_delete_conversation_memory_succeeds_when_memory_disabled(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: None)
    client = TestClient(create_app())
    response = client.delete(
        "/v1/chat/memory/conv-42", headers={"X-Api-Key": "test-key"}
    )

    assert response.status_code == 204

