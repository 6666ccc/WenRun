from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.hospital import checkpointing, graphs


def test_module_graph_is_stateless_and_factory_accepts_saver():
    assert graphs.graph.checkpointer is None
    saver = InMemorySaver()
    assert graphs.build_graph(checkpointer=saver).checkpointer is saver


def test_memory_graph_registry_round_trips():
    sentinel = object()
    try:
        checkpointing.set_memory_graph(sentinel)
        assert checkpointing.get_memory_graph() is sentinel
    finally:
        checkpointing.set_memory_graph(None)


async def test_memory_lifespan_is_noop_without_url(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AI_REDIS_URL", "")
    get_settings.cache_clear()
    try:
        async with checkpointing.memory_lifespan() as saver:
            assert saver is None
            assert checkpointing.get_memory_graph() is None
    finally:
        get_settings.cache_clear()
