import pytest
from langchain_core.messages import AIMessage


class FixedIntentAgent:
    def invoke(self, payload):
        from app.models.intent_result import IntentResult

        return {"structured_response": IntentResult(intent="chat")}


class FakeReplyAgent:
    def invoke(self, payload):
        return {"messages": [AIMessage(content="chat-reply")]}


def _deps():
    from app.graphs.hospital.graph import GraphDependencies

    return GraphDependencies(
        intent_agent=FixedIntentAgent(),
        chat_agent=FakeReplyAgent(),
        hospital_agent=FakeReplyAgent(),
        medical_agent=FakeReplyAgent(),
        clarify_agent=FakeReplyAgent(),
    )


def _state(conversation_id: str, message: str) -> dict:
    return {
        "messages": [{"role": "user", "content": message}],
        "conversation_id": conversation_id,
        "user_id": 1,
        "patient_id": 10,
        "intent": None,
        "memory_enabled": True,
        "task_plan": [],
        "tool_context": {},
        "sources": [],
        "pending_action": None,
        "error": None,
        "retry_count": 0,
    }


def test_graph_config_uses_conversation_as_thread_id():
    from app.graphs.hospital.graph import graph_config

    assert graph_config("c-1", "tok") == {
        "configurable": {
            "thread_id": "c-1",
            "delegation_token": "tok",
        }
    }


def test_get_checkpointer_creates_parent_directory(tmp_path):
    from app.core.config import Settings
    from app.graphs.hospital.checkpoint import get_checkpointer

    checkpoint_file = tmp_path / "nested" / "checkpoints.sqlite"
    settings = Settings(
        dashscope_api_key="test",
        dashscope_base_url="https://example.invalid/v1",
        dashscope_chat_model="test-model",
        embedding_model="test-embedding",
        internal_api_key="internal",
        checkpoint_path=str(checkpoint_file),
    )
    checkpointer = get_checkpointer(settings)
    assert checkpoint_file.parent.exists()
    checkpointer.setup()


def test_checkpoint_is_isolated_by_conversation(tmp_path):
    from app.core.config import Settings
    from app.graphs.hospital.checkpoint import get_checkpointer
    from app.graphs.hospital.graph import build_graph, graph_config

    settings = Settings(
        dashscope_api_key="test",
        dashscope_base_url="https://example.invalid/v1",
        dashscope_chat_model="test-model",
        embedding_model="test-embedding",
        internal_api_key="internal",
        checkpoint_path=str(tmp_path / "checkpoints.sqlite"),
    )
    checkpointer = get_checkpointer(settings)
    graph = build_graph(_deps(), checkpointer=checkpointer)
    graph.invoke(_state("c-1", "会话一"), graph_config("c-1", None))
    graph.invoke(_state("c-2", "会话二"), graph_config("c-2", None))

    state_one = graph.get_state(graph_config("c-1", None)).values
    state_two = graph.get_state(graph_config("c-2", None)).values
    texts_one = [getattr(item, "content", item) for item in state_one["messages"]]
    texts_two = [getattr(item, "content", item) for item in state_two["messages"]]
    assert any("会话一" in str(text) for text in texts_one)
    assert all("会话二" not in str(text) for text in texts_one)
    assert any("会话二" in str(text) for text in texts_two)
    assert all("会话一" not in str(text) for text in texts_two)


@pytest.mark.asyncio
async def test_delete_conversation_removes_checkpoint_and_vector_memory(tmp_path, vector_memory):
    from app.core.config import Settings
    from app.graphs.hospital.checkpoint import get_checkpointer
    from app.graphs.hospital.graph import build_graph, graph_config
    from app.services.chat_service import ChatService

    settings = Settings(
        dashscope_api_key="test",
        dashscope_base_url="https://example.invalid/v1",
        dashscope_chat_model="test-model",
        embedding_model="test-embedding",
        internal_api_key="internal",
        checkpoint_path=str(tmp_path / "checkpoints.sqlite"),
    )
    checkpointer = get_checkpointer(settings)
    graph = build_graph(_deps(), checkpointer=checkpointer)
    graph.invoke(_state("c-1", "需要删除"), graph_config("c-1", None))
    await vector_memory.save_memory("c-1", ["偏好上午就诊"])

    service = ChatService(checkpointer=checkpointer, vector_memory=vector_memory)
    await service.delete_conversation("c-1")
    await service.delete_conversation("c-1")

    assert graph.get_state(graph_config("c-1", None)).values == {}
    assert await vector_memory.load_memory("c-1", "任意查询") == []
