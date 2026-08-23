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
    return _REQUEST_ID.set(request_id)


def reset_request_id(token) -> None:
    _REQUEST_ID.reset(token)


def current_request_id() -> str | None:
    return _REQUEST_ID.get()


def sanitize(text: str | None) -> str:
    value = "" if text is None else str(text)
    value = _SENSITIVE_HEADER.sub(r"\1=[redacted]", value)
    return _BEARER.sub("Bearer [redacted]", value)


def configure_logging() -> None:
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
