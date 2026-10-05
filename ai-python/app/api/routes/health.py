"""最简单的存活检查接口，用于确认 Python HTTP 服务仍在响应。"""

from fastapi import APIRouter, HTTPException, Request
from redis.asyncio import Redis
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.graphs.hospital.checkpointing import get_checkpointer

router = APIRouter(tags=["Health"])


@router.get("/health")
def health() -> dict[str, str]:
    """返回固定状态；此接口不代表模型、Redis 或 Java 都可用。"""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    """Check local dependencies without invoking paid model services."""
    worker = getattr(request.app.state, "rag_worker", None)
    try:
        if worker is None or get_checkpointer() is None:
            raise RuntimeError("dependencies not initialized")
        if not await run_in_threadpool(worker.is_ready):
            raise RuntimeError("worker unavailable")
        async with Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2
        ) as client:
            await client.ping()
    except Exception:  # noqa: BLE001 - dependency failures share no common base
        # Never expose connection strings, credentials, or exception bodies.
        raise HTTPException(
            status_code=503, detail="Service dependencies unavailable"
        ) from None
    return {"status": "ready"}
