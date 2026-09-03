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
                "data": (AIMessageChunk(content='{"selected_agents":["chat"]}'), {"langgraph_node": "begin_node"}),
            }
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="你好"), {"langgraph_node": "chat_node"}),
            }
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="，有什么可以帮您？"), {"langgraph_node": "chat_node"}),
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


def test_chat_stream_hides_knowledge_internals_when_final_node_summarizes(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)

    class FakeGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {
                "type": "values",
                "data": {"selected_agents": ["knowledge", "tools"]},
            }
            # 工具输出绝不能作为面向患者的文本发送。
            yield {
                "type": "messages",
                "data": (ToolMessage(content="RAW_SEARCH_RESULT", tool_call_id="call-1"), {"langgraph_node": "knowledge_node"}),
            }
            # 多意图时 final_node 会重写正文，此前各节点的输出都属于内部内容。
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="内部检索摘要"), {"langgraph_node": "knowledge_node"}),
            }
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="最终面向患者的答案"), {"langgraph_node": "final_node"}),
            }
            yield {
                "type": "values",
                "data": {
                    "selected_agents": ["knowledge", "tools"],
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
            "message": "感冒吃什么药，顺便帮我查下明天内科的号",
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


def test_chat_stream_forwards_knowledge_node_when_knowledge_is_the_sole_agent(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)

    class FakeGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {
                "type": "values",
                "data": {"selected_agents": ["knowledge"]},
            }
            # 嵌套 Agent（网页兜底）的分片带子图命名空间，不得转发给患者。
            yield {
                "type": "messages",
                "ns": ("knowledge_node:1",),
                "data": (AIMessageChunk(content="嵌套内部草稿"), {"langgraph_node": "model"}),
            }
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="院内资料显示，"), {"langgraph_node": "knowledge_node"}),
            }
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="请多休息。"), {"langgraph_node": "knowledge_node"}),
            }
            yield {
                "type": "values",
                "data": {
                    "selected_agents": ["knowledge"],
                    "final_reply": "院内资料显示，请多休息。",
                    "rag_sources": [{"id": "S1", "title": "院内资料", "page": 1}],
                },
            }

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={
            "message": "感冒吃什么药",
            "conversationId": "knowledge-sole-demo",
        },
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert [event["type"] for event in events] == [
        "status",
        "status",
        "status",
        "token",
        "token",
        "citation",
        "done",
    ]
    assert [event["content"] for event in events if event["type"] == "token"] == [
        "院内资料显示，",
        "请多休息。",
    ]
    assert "嵌套内部草稿" not in response.text
    assert events[-1]["reply"] == "院内资料显示，请多休息。"


def test_stream_visible_nodes_streams_the_sole_root_reply_node():
    assert chat_route._stream_visible_nodes(["chat"]) == {"chat_node"}
    assert chat_route._stream_visible_nodes(["knowledge"]) == {"knowledge_node"}
    # tool_node 的正文由嵌套 Agent 生成，只能等 final_node 透传后一次性下发。
    assert chat_route._stream_visible_nodes(["tools"]) == {"final_node"}
    assert chat_route._stream_visible_nodes(["knowledge", "chat"]) == {"final_node"}
    assert chat_route._stream_visible_nodes([]) == {"final_node"}


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


def test_stream_visible_nodes_uses_fast_node_in_fast_mode():
    assert chat_route._stream_visible_nodes([], fast_mode=True) == {"fast_node"}
    assert chat_route._stream_visible_nodes(["chat"], fast_mode=True) == {"fast_node"}


def test_chat_stream_uses_fast_graph_when_fast_mode_enabled(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)

    class NormalGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            raise AssertionError("fastMode=true 时不得使用正常图")
            yield  # pragma: no cover

    class FastGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {
                "type": "messages",
                "data": (AIMessageChunk(content="快速回复"), {"langgraph_node": "fast_node"}),
            }
            yield {"type": "values", "data": {"final_reply": "快速回复", "rag_sources": []}}

    monkeypatch.setattr(chat_route, "graph", NormalGraph())
    monkeypatch.setattr(chat_route, "fast_graph", FastGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={
            "message": "你好",
            "conversationId": "fast-demo",
            "memoryEnabled": False,
            "fastMode": True,
        },
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert [event["type"] for event in events] == ["status", "token", "done"]
    assert events[1]["content"] == "快速回复"
    assert events[-1]["reply"] == "快速回复"


def test_chat_stream_fast_mode_suppresses_knowledge_status_from_leftover_agents(
    monkeypatch,
):
    """快速模式不得因 checkpoint 残留 selected_agents 串出知识检索状态。"""
    headers = _chat_auth_headers(monkeypatch)

    class FastGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            # 模拟上一轮正常模式留下的 knowledge；fast_node 清空前也可能先看到。
            yield {
                "type": "values",
                "data": {"selected_agents": ["knowledge"]},
            }
            yield {
                "type": "messages",
                "data": (
                    AIMessageChunk(content="快速回复"),
                    {"langgraph_node": "fast_node"},
                ),
            }
            yield {
                "type": "values",
                "data": {
                    "final_reply": "快速回复",
                    "rag_sources": [],
                    "selected_agents": [],
                },
            }

    monkeypatch.setattr(chat_route, "fast_graph", FastGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={
            "message": "你好",
            "conversationId": "fast-leftover-agents",
            "memoryEnabled": False,
            "fastMode": True,
        },
    )

    assert response.status_code == 200
    events = _sse_events(response)
    status_contents = [
        event["content"] for event in events if event.get("type") == "status"
    ]
    assert "正在检索相关资料…" not in status_contents
    assert "正在整理答案…" not in status_contents
    assert any(event.get("type") == "token" for event in events)
    done = next(event for event in events if event.get("type") == "done")
    assert done["selectedAgents"] == []


def test_chat_stream_defaults_to_normal_graph(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)

    class NormalGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {"type": "values", "data": {"final_reply": "正常回复"}}

    class FastGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            raise AssertionError("未传 fastMode 时不得使用快速图")
            yield  # pragma: no cover

    monkeypatch.setattr(chat_route, "graph", NormalGraph())
    monkeypatch.setattr(chat_route, "fast_graph", FastGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={"message": "你好", "conversationId": "fast-default", "memoryEnabled": False},
    )

    assert _sse_events(response)[-1]["reply"] == "正常回复"


def test_chat_stream_prefers_fast_memory_graph(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    from app.graphs.hospital import checkpointing

    captured: dict = {}

    class FastMemoryGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["config"] = config
            yield {"type": "values", "data": {"final_reply": "快速记忆回复"}}

    class FastStatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["used_stateless"] = True
            yield {"type": "values", "data": {"final_reply": "快速无记忆回复"}}

    monkeypatch.setattr(chat_route, "fast_graph", FastStatelessGraph())
    checkpointing.set_fast_memory_graph(FastMemoryGraph())
    try:
        client = TestClient(create_app())
        response = client.post(
            "/v1/chat/stream",
            headers=headers,
            json={"message": "你好", "conversationId": "conv-77", "fastMode": True},
        )
    finally:
        checkpointing.set_fast_memory_graph(None)

    assert _sse_events(response)[-1]["reply"] == "快速记忆回复"
    assert captured["config"] == {"configurable": {"thread_id": "conv-77"}}
    assert "used_stateless" not in captured

