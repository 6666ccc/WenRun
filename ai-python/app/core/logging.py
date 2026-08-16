import re

from loguru import logger

_SENSITIVE_HEADER = re.compile(
    r"(?i)\b(authorization|x-delegated-token|x-api-key)\b\s*[:=]\s*(?:bearer\s+)?\S+"
)
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")


def sanitize(text: str | None) -> str:
    value = "" if text is None else str(text)
    value = _SENSITIVE_HEADER.sub(r"\1=[redacted]", value)
    return _BEARER.sub("Bearer [redacted]", value)


def configure_logging() -> None:
    logger.remove()
    logger.add(
        lambda message: print(sanitize(str(message)), end=""),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )


def log_event(
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    node: str | None = None,
    tool: str | None = None,
    duration_ms: int | None = None,
    error_code: str | None = None,
) -> None:
    logger.info(
        "ai_event request_id={} conversation_id={} node={} tool={} duration_ms={} error_code={}",
        request_id,
        conversation_id,
        node,
        tool,
        duration_ms,
        error_code,
    )
