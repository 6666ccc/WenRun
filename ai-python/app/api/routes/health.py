"""最简单的存活检查接口，用于确认 Python HTTP 服务仍在响应。"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def health() -> dict[str, str]:
    """返回固定状态；此接口不代表模型、Redis 或 Java 都可用。"""
    return {"status": "ok"}
