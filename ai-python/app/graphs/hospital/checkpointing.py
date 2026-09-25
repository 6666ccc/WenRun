"""管理 Redis 检查点，以及使用它编译出的两张可恢复对话图。

检查点保存图运行到哪里。写工具调用 interrupt() 等待确认后，/resume 才能
找到原来的位置继续。如果 Redis 未配置或连接失败，就退回无检查点的图；
这时普通聊天仍可运行，但路由会关闭需要 HITL 的写工具。
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.graphs import build_fast_graph, build_graph

_memory_graph: Any | None = None
_checkpointer: Any | None = None
_fast_memory_graph: Any | None = None

# 这三个进程内变量只保存“当前可用的图/连接”，不是患者的对话内容。


def get_memory_graph() -> Any | None:
    """取得当前可用的普通带检查点图；服务未连接 Redis 时为空。"""
    return _memory_graph


def set_memory_graph(graph: Any | None) -> None:
    """服务启动/关闭时登记或清除普通带检查点图。"""
    global _memory_graph
    _memory_graph = graph


def get_fast_memory_graph() -> Any | None:
    """取得当前可用的快速带检查点图。"""
    return _fast_memory_graph


def set_fast_memory_graph(graph: Any | None) -> None:
    """服务启动/关闭时登记或清除快速带检查点图。"""
    global _fast_memory_graph
    _fast_memory_graph = graph


def get_checkpointer() -> Any | None:
    """取得当前检查点存储器，供清除单个会话进度的接口使用。"""
    return _checkpointer


def _set_checkpointer(saver: Any | None) -> None:
    """内部登记或清除检查点存储器。"""
    global _checkpointer
    _checkpointer = saver


@asynccontextmanager
async def memory_lifespan() -> AsyncIterator[Any | None]:
    """在服务生命周期内连接 Redis；失败时让只读、无记忆聊天继续工作。"""
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
    # 普通图和快速图共用同一检查点存储，但节点结构各不相同。
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
