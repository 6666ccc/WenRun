import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver


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


@pytest.mark.asyncio
async def test_get_chat_service_is_singleton(monkeypatch):
    from app.services import chat_service as mod
    from app.services.chat_service import ChatService

    mod.reset_chat_service()
    created = []

    async def fake_create():
        service = ChatService(graph=object())
        created.append(service)
        return service

    monkeypatch.setattr(mod, "create_chat_service", fake_create)
    first = await mod.get_chat_service()
    second = await mod.get_chat_service()
    assert first is second
    assert len(created) == 1
    mod.reset_chat_service()


@pytest.mark.asyncio
async def test_create_chat_service_compiles_injected_graph():
    from app.services.chat_service import create_chat_service

    service = await create_chat_service(deps=_deps(), checkpointer=MemorySaver())
    assert service._graph is not None
    assert service._checkpointer is not None
