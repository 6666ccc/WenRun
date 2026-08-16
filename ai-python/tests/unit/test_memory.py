import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.mark.asyncio
async def test_memory_is_filtered_by_conversation(vector_memory):
    await vector_memory.save_memory("c-1", ["偏好上午就诊"])
    await vector_memory.save_memory("c-2", ["对青霉素过敏"])
    assert await vector_memory.load_memory("c-1", "就诊") == ["偏好上午就诊"]


@pytest.mark.asyncio
async def test_memory_disabled_skips_vector_store(memory_node, spy_store):
    await memory_node({"conversation_id": "c-1", "memory_enabled": False})
    assert spy_store.calls == []


def test_trim_messages_keeps_latest_within_budget():
    from app.services.memory.window import trim_messages

    messages = [
        HumanMessage(content="旧消息一" * 20),
        AIMessage(content="旧回复一" * 20),
        HumanMessage(content="最新问题"),
    ]
    result = trim_messages(messages, token_budget=20)
    assert result.kept[-1].content == "最新问题"
    assert result.overflow
    assert result.kept[0] not in result.overflow


def test_vector_memory_filter_uses_conversation_id():
    from qdrant_client.models import FieldCondition, MatchValue

    from app.services.memory.vector import conversation_filter

    qdrant_filter = conversation_filter("c-1")
    condition = qdrant_filter.must[0]
    assert isinstance(condition, FieldCondition)
    assert condition.key == "metadata.conversationId"
    assert isinstance(condition.match, MatchValue)
    assert condition.match.value == "c-1"
