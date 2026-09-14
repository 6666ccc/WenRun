"""Redis checkpointer 生命周期和带记忆图的进程内注册表。"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.graphs import build_fast_graph, build_graph

_memory_graph: Any | None = None
_checkpointer: Any | None = None
_fast_memory_graph: Any | None = None


def get_memory_graph() -> Any | None:
    return _memory_graph


def set_memory_graph(graph: Any | None) -> None:
    global _memory_graph
    _memory_graph = graph


def get_fast_memory_graph() -> Any | None:
    return _fast_memory_graph


def set_fast_memory_graph(graph: Any | None) -> None:
    global _fast_memory_graph
    _fast_memory_graph = graph


def get_checkpointer() -> Any | None:
    return _checkpointer


def _set_checkpointer(saver: Any | None) -> None:
    global _checkpointer
    _checkpointer = saver


@asynccontextmanager
async def memory_lifespan() -> AsyncIterator[Any | None]:
    settings = get_settings()
    if not settings.redis_url:
        logger.warning("checkpointer_disabled reason=AI_REDIS_URL_not_configured")
        yield None
        return

    from langgraph.checkpoint.redis.ashallow import AsyncShallowRedisSaver

    ttl = {
        "default_ttl": settings.checkpoint_ttl_minutes,
        "refresh_on_read": True,
    }
    stack = AsyncExitStack()
    try:
        saver = await stack.enter_async_context(
            AsyncShallowRedisSaver.from_conn_string(settings.redis_url, ttl=ttl)
        )
        await saver.asetup()
    except Exception:  # noqa: BLE001 - Redis/saver errors share no stable base
        logger.exception("checkpointer_setup_failed falling_back_to_stateless_graph")
        await stack.aclose()
        yield None
        return

    _set_checkpointer(saver)
    set_memory_graph(build_graph(checkpointer=saver))
    set_fast_memory_graph(build_fast_graph(checkpointer=saver))
    logger.info("checkpointer_ready ttl_minutes={}", settings.checkpoint_ttl_minutes)
    try:
        yield saver
    finally:
        set_memory_graph(None)
        set_fast_memory_graph(None)
        _set_checkpointer(None)
        await stack.aclose()
