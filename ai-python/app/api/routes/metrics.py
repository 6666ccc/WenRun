from fastapi import APIRouter, Depends

from app.api.dependencies.auth import verify_api_key
from app.intent.metrics import route_metrics_snapshot
from app.observability.context_metrics import context_metrics_snapshot

router = APIRouter(
    prefix="/v1/metrics",
    tags=["Metrics"],
    dependencies=[Depends(verify_api_key)],
)


@router.get("/intent-routing")
def intent_routing_metrics() -> dict:
    """返回当前 Python 进程的级联路由统计，不包含患者原文或身份信息。"""

    return route_metrics_snapshot()


@router.get("/context")
def context_metrics() -> dict:
    """返回当前进程的脱敏上下文用量、延迟和错误统计。"""

    return context_metrics_snapshot()
