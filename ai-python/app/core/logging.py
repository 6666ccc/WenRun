"""请求追踪号和日志脱敏。

同一次 HTTP 请求中的各节点都可读取追踪号；写日志时遮住 API 密钥和令牌。
"""

import re
import sys
from contextvars import ContextVar
from uuid import uuid4

from loguru import logger

_SENSITIVE_HEADER = re.compile(
    r"(?i)\b(authorization|x-delegated-token|x-api-key)\b\s*[:=]\s*(?:bearer\s+)?\S+"
)
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")
_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id(incoming: str | None) -> str:
    """保留合理长度的上游追踪号；没有时创建一个新的 UUID。"""
    if incoming and len(incoming) <= 64 and all(not char.isspace() for char in incoming):
        return incoming
    return str(uuid4())


def set_request_id(request_id: str):
    """把追踪号放进当前异步请求自己的上下文。"""
    return _REQUEST_ID.set(request_id)


def reset_request_id(token) -> None:
    """请求结束时恢复原上下文，避免影响其他请求。"""
    _REQUEST_ID.reset(token)


def current_request_id() -> str | None:
    """读取本次请求的追踪号，供工具回调 Java 时一并传递。"""
    return _REQUEST_ID.get()


def sanitize(text: str | None) -> str:
    """遮住日志文本中常见的认证请求头和 Bearer 令牌。"""
    value = "" if text is None else str(text)
    value = _SENSITIVE_HEADER.sub(r"\1=[redacted]", value)
    return _BEARER.sub("Bearer [redacted]", value)


def configure_logging() -> None:
    """在服务启动时注册统一的日志输出和脱敏过滤。"""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        # 不指定 format 和 colorize，使用 Loguru 默认格式，并根据终端自动判断是否着色。
        filter=_sanitize_record,
    )


def _sanitize_record(record: dict) -> bool:
    """保留默认日志格式的同时，避免敏感信息进入日志。"""
    record["message"] = sanitize(record["message"])
    return True
