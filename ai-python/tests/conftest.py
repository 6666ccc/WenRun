import os

import pytest


_REQUIRED_TEST_ENV = {
    "DASHSCOPE_API_KEY": "test-api-key",
    "DASHSCOPE_BASE_URL": "https://example.invalid/v1",
    "DASHSCOPE_CHAT_MODEL": "test-chat-model",
    "EMBEDDING_MODEL": "test-embedding-model",
    "AI_INTERNAL_API_KEY": "test-internal-api-key",
}

for name, value in _REQUIRED_TEST_ENV.items():
    os.environ.setdefault(name, value)


class FakeMedicalAgent:
    """Deterministic medical-agent double. Never calls a live model."""

    def invoke(self, payload):
        text = payload if isinstance(payload, str) else _payload_text(payload)
        if "胸痛" in text or "呼吸困难" in text:
            answer = "出现胸痛或呼吸困难时，请立即前往急诊或呼叫急救，不要延误。"
        else:
            answer = "这是一般健康科普，不能替代线下就医。"
        if isinstance(payload, str):
            return answer
        from langchain_core.messages import AIMessage

        return {"messages": [AIMessage(content=answer)]}


def _payload_text(payload) -> str:
    if isinstance(payload, dict) and payload.get("messages"):
        last = payload["messages"][-1]
        if isinstance(last, dict):
            return str(last.get("content", ""))
        return str(getattr(last, "content", last))
    return str(payload)


@pytest.fixture
def fake_medical_agent():
    return FakeMedicalAgent()


class FakeVectorStores:
    """In-memory store double. Records the collection retrieve() asked for."""

    def __init__(self):
        self.last_collection = None
        self.pairs = []

    def for_collection(self, collection: str):
        self.last_collection = collection
        return self

    def similarity_search_with_score(self, query, k=4, filter=None):
        return list(self.pairs)


@pytest.fixture
def fake_vector_stores():
    stores = FakeVectorStores()
    from app.rag.rag import set_vector_stores

    set_vector_stores(stores)
    try:
        yield stores
    finally:
        set_vector_stores(None)


class SpyStore:
    def __init__(self):
        self.calls = []


@pytest.fixture
def spy_store():
    return SpyStore()


@pytest.fixture
def vector_memory():
    from app.services.memory.vector import VectorMemory

    return VectorMemory()


@pytest.fixture
def memory_node(spy_store):
    from app.graphs.hospital.graph import GraphDependencies
    from app.graphs.hospital.nodes.memory_node import build_load_memory_node
    from app.services.memory.vector import VectorMemory

    deps = GraphDependencies(
        intent_agent=None,
        chat_agent=None,
        hospital_agent=None,
        medical_agent=None,
        vector_memory=VectorMemory(store=spy_store),
    )
    node = build_load_memory_node(deps)

    async def _async_node(state):
        return node(state)

    return _async_node
