import json
from base64 import b64encode
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
from fastapi.testclient import TestClient
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
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


def _chat_auth_headers(monkeypatch, **claim_overrides) -> dict[str, str]:
    signing_key = b"a" * 32
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    monkeypatch.setenv("AI_DELEGATION_SIGNING_SECRET", b64encode(signing_key).decode())
    get_settings.cache_clear()
    now = datetime.now(UTC)
    claims = {
        "iss": "wenrun-java",
        "sub": "1",
        "patientId": 12,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(claim_overrides)
    delegated_token = jwt.encode(
        claims,
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

    def fake_ingest_file(content, filename, **lifecycle):
        captured["content"] = content
        captured["filename"] = filename
        captured["lifecycle"] = lifecycle
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
        "lifecycle": {
            "document_id": None,
            "uploaded_by": 0,
            "effective_from": None,
            "expires_at": None,
            "force_rebuild": False,
        },
    }


def test_upload_knowledge_document_returns_bad_request_for_invalid_file(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    def fake_ingest_file(content, filename, **lifecycle):
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


def test_knowledge_document_lifecycle_endpoints(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()
    calls = []
    monkeypatch.setattr(
        chat_route,
        "get_document_versions",
        lambda document_id: [{"document_id": document_id, "version": 2, "status": "active"}],
    )
    monkeypatch.setattr(
        chat_route,
        "deactivate_document",
        lambda document_id: calls.append(("deactivate", document_id)) or 1,
    )
    monkeypatch.setattr(
        chat_route,
        "delete_document",
        lambda document_id: calls.append(("delete", document_id)) or 2,
    )
    client = TestClient(create_app())
    headers = {"X-Api-Key": "test-key"}

    inspected = client.get("/v1/chat/documents/doc-1", headers=headers)
    deactivated = client.post(
        "/v1/chat/documents/doc-1/deactivate", headers=headers
    )
    deleted = client.delete("/v1/chat/documents/doc-1", headers=headers)

    assert inspected.status_code == 200
    assert inspected.json()["versions"][0]["version"] == 2
    assert deactivated.json() == {
        "documentId": "doc-1",
        "status": "inactive",
        "versions": 1,
    }
    assert deleted.json() == {"documentId": "doc-1", "deletedVersions": 2}
    assert calls == [("deactivate", "doc-1"), ("delete", "doc-1")]


def test_rebuild_knowledge_document_forces_new_version(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()
    captured = {}

    def fake_ingest_file(content, filename, **lifecycle):
        captured.update(content=content, filename=filename, lifecycle=lifecycle)
        return {"document_id": lifecycle["document_id"], "version": 3}

    monkeypatch.setattr(chat_route, "ingest_file", fake_ingest_file)
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/documents/doc-1/rebuild?uploadedBy=9",
        headers={"X-Api-Key": "test-key"},
        files={"file": ("guide.txt", b"new guide", "text/plain")},
    )

    assert response.status_code == 201
    assert response.json() == {"document_id": "doc-1", "version": 3}
    assert captured["lifecycle"] == {
        "document_id": "doc-1",
        "uploaded_by": 9,
        "effective_from": None,
        "expires_at": None,
        "force_rebuild": True,
    }


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


def test_chat_stream_rejects_payload_user_that_differs_from_delegation(monkeypatch):
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=_chat_auth_headers(monkeypatch),
        json={
            "message": "你好",
            "conversationId": "identity-user",
            "userContext": {"userId": 2, "patientId": 12},
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "delegated user identity mismatch"}


def test_chat_stream_rejects_payload_patient_that_differs_from_delegation(monkeypatch):
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=_chat_auth_headers(monkeypatch),
        json={
            "message": "你好",
            "conversationId": "identity-patient",
            "userContext": {"userId": 1, "patientId": 99},
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "delegated patient identity mismatch"}


def test_chat_stream_rejects_non_numeric_delegated_subject(monkeypatch):
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=_chat_auth_headers(monkeypatch, sub="not-a-user"),
        json={"message": "你好", "conversationId": "identity-invalid"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid delegated token"}


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


def test_graph_config_uses_user_scoped_conversation_id_as_thread_id():
    from app.models.chat import ChatRequest

    request = ChatRequest(message="你好", conversationId="conv-42")
    delegation = SimpleNamespace(identity=SimpleNamespace(user_id=1))

    assert chat_route._graph_config(request, delegation) == {
        "configurable": {"thread_id": "user:1:conversation:conv-42"}
    }
    assert chat_route.thread_id_for(2, "conv-42") != chat_route.thread_id_for(1, "conv-42")


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
    assert captured["config"] == {
        "configurable": {"thread_id": "user:1:conversation:conv-42"}
    }
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
        "/v1/chat/memory/conv-42?userId=1", headers={"X-Api-Key": "test-key"}
    )

    assert response.status_code == 204
    assert deleted == ["user:1:conversation:conv-42"]


def test_delete_conversation_memory_succeeds_when_memory_disabled(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: None)
    client = TestClient(create_app())
    response = client.delete(
        "/v1/chat/memory/conv-42?userId=1", headers={"X-Api-Key": "test-key"}
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
    assert captured["config"] == {
        "configurable": {"thread_id": "user:1:conversation:conv-77"}
    }
    assert "used_stateless" not in captured


def test_chat_stream_emits_confirm_event_when_graph_pauses_for_approval(monkeypatch):
    """写工具挂起时必须发 confirm，而不是把空 final_reply 打成 500。"""

    headers = _chat_auth_headers(monkeypatch)

    class PausedGraph:
        # 有 checkpointer 才会开启写能力，也才能读到挂起的确认请求。
        checkpointer = object()

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            assert context.writes_enabled is True
            assert context.conversation_id == "conversation-1"
            yield {"type": "values", "data": {"selected_agents": ["tools"]}}

        async def aget_state(self, config):
            return SimpleNamespace(interrupts=(
                SimpleNamespace(
                    id="int-1",
                    value={
                        "kind": "registration_create",
                        "prompt": "请确认是否为您挂 2026-09-04 下午 内科 张伟 的号",
                        "detail": {"scheduleId": 9, "staffName": "张伟"},
                    },
                ),
            ))

    monkeypatch.setattr(chat_route, "graph", PausedGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={"message": "帮我挂明天下午张伟的号", "conversationId": "conversation-1"},
    )

    assert response.status_code == 200
    events = _sse_events(response)
    types = [event["type"] for event in events]
    assert "confirm" in types
    assert "done" not in types
    confirm = next(event for event in events if event["type"] == "confirm")
    assert confirm["kind"] == "registration_create"
    assert confirm["detail"]["scheduleId"] == 9
    assert confirm["conversationId"] == "conversation-1"
    assert confirm["interruptId"] == "int-1"


def test_chat_stream_keeps_writes_disabled_without_a_checkpointer(monkeypatch):
    """无记忆会话恢复不了中断，必须关掉写能力，否则整轮会静默失败。"""

    headers = _chat_auth_headers(monkeypatch)

    class StatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            assert context.writes_enabled is False
            yield {"type": "values", "data": {"final_reply": "已生成回复", "selected_agents": ["tools"]}}

    monkeypatch.setattr(chat_route, "graph", StatelessGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={"message": "帮我挂号", "conversationId": "conversation-2", "memoryEnabled": False},
    )

    assert [event["type"] for event in _sse_events(response)][-1] == "done"


def test_chat_resume_forwards_decision_into_the_graph(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {}

    class ResumedGraph:
        checkpointer = object()

        def __init__(self):
            self._resumed = False

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["input"] = state
            captured["thread_id"] = config["configurable"]["thread_id"]
            self._resumed = True
            yield {
                "type": "values",
                "data": {"final_reply": "挂号已办好。", "selected_agents": ["tools"]},
            }

        async def aget_state(self, config):
            if self._resumed:
                return SimpleNamespace(interrupts=())
            return SimpleNamespace(interrupts=(
                SimpleNamespace(id="int-1", value={"kind": "registration_create"}),
            ))

    monkeypatch.setattr(chat_route, "graph", ResumedGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/resume",
        headers=headers,
        json={"conversationId": "conversation-1", "decision": "approve"},
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert events[-1]["type"] == "done"
    assert events[-1]["reply"] == "挂号已办好。"
    assert captured["thread_id"] == "user:1:conversation:conversation-1"
    assert captured["input"].resume == {"int-1": "approve"}


def test_chat_resume_rejects_unknown_decision(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    client = TestClient(create_app())

    response = client.post(
        "/v1/chat/resume",
        headers=headers,
        json={"conversationId": "conversation-1", "decision": "maybe"},
    )

    assert response.status_code == 422


def test_chat_resume_rejects_other_pending_interrupts(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {}

    class ResumedGraph:
        checkpointer = object()

        def __init__(self):
            self._resumed = False

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["input"] = state
            self._resumed = True
            yield {
                "type": "values",
                "data": {"final_reply": "挂号已办好。", "selected_agents": ["tools"]},
            }

        async def aget_state(self, config):
            if self._resumed:
                return SimpleNamespace(interrupts=())
            return SimpleNamespace(interrupts=(
                SimpleNamespace(id="int-1", value={"kind": "registration_create"}),
                SimpleNamespace(id="int-2", value={"kind": "registration_cancel"}),
            ))

    monkeypatch.setattr(chat_route, "graph", ResumedGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/resume",
        headers=headers,
        json={
            "conversationId": "conversation-1",
            "decision": "approve",
            "interruptId": "int-1",
        },
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert events[-1]["type"] == "done"
    assert captured["input"].resume == {"int-1": "approve", "int-2": "reject"}


def test_chat_resume_errors_without_running_graph_when_multiple_interrupts_lack_id(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {"astream": 0, "deleted": []}

    class FakeSaver:
        async def adelete_thread(self, conversation_id):
            captured["deleted"].append(conversation_id)

    class ConflictedGraph:
        checkpointer = object()

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["astream"] += 1
            yield {"type": "values", "data": {"final_reply": "不应执行", "selected_agents": ["tools"]}}

        async def aget_state(self, config):
            return SimpleNamespace(interrupts=(
                SimpleNamespace(id="int-1", value={"kind": "registration_create"}),
                SimpleNamespace(id="int-2", value={"kind": "registration_cancel"}),
            ))

    monkeypatch.setattr(chat_route, "graph", ConflictedGraph())
    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: FakeSaver())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/resume",
        headers=headers,
        json={"conversationId": "conversation-1", "decision": "approve"},
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "AI_RESUME_CONFLICT"
    assert events[-1]["message"] == "请重新发起挂号"
    assert captured["astream"] == 0
    assert captured["deleted"] == []


def test_chat_stream_preserves_pending_interrupt_instead_of_running(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {"deleted": [], "astream": 0}

    class FakeSaver:
        async def adelete_thread(self, conversation_id):
            captured["deleted"].append(conversation_id)

    class StaleGraph:
        checkpointer = object()

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["astream"] += 1
            yield {
                "type": "values",
                "data": {"final_reply": "不应执行", "selected_agents": ["chat"]},
            }

        async def aget_state(self, config):
            return SimpleNamespace(interrupts=(
                SimpleNamespace(
                    id="int-old",
                    value={
                        "kind": "registration_create",
                        "prompt": "请确认原挂号操作",
                        "detail": {"scheduleId": 9},
                    },
                ),
            ))

    monkeypatch.setattr(chat_route, "graph", StaleGraph())
    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: FakeSaver())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={"message": "改挂明天的号", "conversationId": "conversation-1"},
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert events == [{
        "type": "confirm",
        "conversationId": "conversation-1",
        "kind": "registration_create",
        "prompt": "请确认原挂号操作",
        "detail": {"scheduleId": 9},
        "interruptId": "int-old",
    }]
    assert captured["deleted"] == []
    assert captured["astream"] == 0


def test_chat_stream_rehydrates_empty_checkpoint_from_authoritative_history(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {}

    class RecoveryGraph:
        checkpointer = object()

        async def aget_state(self, config):
            return SimpleNamespace(values={}, interrupts=())

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["messages"] = state["messages"]
            yield {"type": "values", "data": {"final_reply": "恢复成功", "selected_agents": ["chat"]}}

    monkeypatch.setattr(chat_route, "graph", RecoveryGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={
            "message": "现在怎么办？",
            "conversationId": "conversation-recovery",
            "recoveryMessages": [
                {"id": 1, "role": "user", "content": "我昨天挂了号"},
                {"id": 2, "role": "assistant", "content": "请携带身份证就诊"},
            ],
        },
    )

    assert response.status_code == 200
    assert _sse_events(response)[-1]["reply"] == "恢复成功"
    assert [message.content for message in captured["messages"]] == [
        "我昨天挂了号",
        "请携带身份证就诊",
        "现在怎么办？",
    ]
    assert isinstance(captured["messages"][0], HumanMessage)
    assert isinstance(captured["messages"][1], AIMessage)


def test_chat_stream_does_not_duplicate_recovery_history_on_checkpoint_hit(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {}

    class ExistingGraph:
        checkpointer = object()

        async def aget_state(self, config):
            return SimpleNamespace(values={"messages": [HumanMessage(content="checkpoint history")]}, interrupts=())

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["messages"] = state["messages"]
            yield {"type": "values", "data": {"final_reply": "正常续聊", "selected_agents": ["chat"]}}

    monkeypatch.setattr(chat_route, "graph", ExistingGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={
            "message": "继续",
            "conversationId": "conversation-hit",
            "recoveryMessages": [{"id": 1, "role": "user", "content": "不得重复注入"}],
        },
    )

    assert response.status_code == 200
    assert [message.content for message in captured["messages"]] == ["继续"]


def test_chat_stream_places_confirmed_long_term_preferences_in_state(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {}

    class FakeGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["memories"] = state.get("long_term_memories")
            yield {"type": "values", "data": {"final_reply": "好的", "selected_agents": ["chat"]}}

    monkeypatch.setattr(chat_route, "graph", FakeGraph())
    response = TestClient(create_app()).post(
        "/v1/chat/stream",
        headers=headers,
        json={
            "message": "你好",
            "conversationId": "new-conversation",
            "longTermMemories": [{
                "memoryId": "memory-1",
                "type": "communication_preference",
                "content": "回复简短",
                "status": "active",
            }],
        },
    )

    assert response.status_code == 200
    assert captured["memories"][0]["content"] == "回复简短"

