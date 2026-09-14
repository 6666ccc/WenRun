"""Per-turn context metrics without patient text, tokens, or tool payloads."""

import hashlib
import json
import os
from collections import Counter, deque
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from threading import Lock
from time import perf_counter

from loguru import logger

PROMPT_VERSION = "hospital-agent-v3"
CONTEXT_SCHEMA_VERSION = "context-v2"


@dataclass
class ContextTrace:
    request_id: str | None
    thread_hash: str
    mode: str
    checkpoint_hit: bool
    rehydrated: bool
    started_at: float = field(default_factory=perf_counter)
    summary_version: int | None = None
    input_tokens_by_source: dict[str, int] = field(default_factory=dict)
    memory_count: int = 0
    rag_count: int = 0
    tool_names: set[str] = field(default_factory=set)
    node_names: set[str] = field(default_factory=set)
    first_token_ms: int | None = None
    error_code: str | None = None
    _token: Token | None = field(default=None, repr=False)
    _finished: bool = field(default=False, repr=False)

    def finish(self, *, error_code: str | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        if error_code:
            self.error_code = error_code
        payload = {
            "event": "context_trace",
            "request_id": self.request_id,
            "thread_hash": self.thread_hash,
            "mode": self.mode,
            "checkpoint_hit": self.checkpoint_hit,
            "rehydrated": self.rehydrated,
            "summary_version": self.summary_version,
            "input_tokens_by_source": dict(sorted(self.input_tokens_by_source.items())),
            "memory_count": self.memory_count,
            "rag_count": self.rag_count,
            "tool_names": sorted(self.tool_names),
            "node_names": sorted(self.node_names),
            "first_token_ms": self.first_token_ms,
            "total_ms": round((perf_counter() - self.started_at) * 1000),
            "error_code": self.error_code,
            "prompt_version": PROMPT_VERSION,
            "context_schema_version": CONTEXT_SCHEMA_VERSION,
            "model_name": os.getenv("DASHSCOPE_CHAT_MODEL", "unknown"),
        }
        logger.info("context_trace {}", json.dumps(payload, ensure_ascii=False, sort_keys=True))
        _record_snapshot(payload)
        if self._token is not None:
            _CURRENT_TRACE.reset(self._token)


_CURRENT_TRACE: ContextVar[ContextTrace | None] = ContextVar(
    "context_trace", default=None
)
_METRICS_LOCK = Lock()
_MODE_COUNTS: Counter[str] = Counter()
_ERROR_COUNTS: Counter[str] = Counter()
_TOTAL_MS: deque[int] = deque(maxlen=500)
_FIRST_TOKEN_MS: deque[int] = deque(maxlen=500)
_TOKEN_TOTALS: Counter[str] = Counter()
_COMPLETED = 0


def _record_snapshot(payload: dict) -> None:
    global _COMPLETED
    with _METRICS_LOCK:
        _COMPLETED += 1
        _MODE_COUNTS[str(payload["mode"])] += 1
        if payload.get("error_code"):
            _ERROR_COUNTS[str(payload["error_code"])] += 1
        if isinstance(payload.get("total_ms"), int):
            _TOTAL_MS.append(payload["total_ms"])
        if isinstance(payload.get("first_token_ms"), int):
            _FIRST_TOKEN_MS.append(payload["first_token_ms"])
        for source, count in payload.get("input_tokens_by_source", {}).items():
            if isinstance(count, int):
                _TOKEN_TOTALS[str(source)] += count


def _p95(values: deque[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, (len(ordered) * 95 + 99) // 100 - 1)]


def context_metrics_snapshot() -> dict:
    """Low-cardinality, current-process snapshot suitable for scraping."""

    with _METRICS_LOCK:
        return {
            "completed": _COMPLETED,
            "modeCounts": dict(_MODE_COUNTS),
            "errorCounts": dict(_ERROR_COUNTS),
            "p95TotalMs": _p95(_TOTAL_MS),
            "p95FirstTokenMs": _p95(_FIRST_TOKEN_MS),
            "inputTokenTotalsBySource": dict(_TOKEN_TOTALS),
            "scope": "current_process",
            "containsPatientText": False,
        }


def begin_context_trace(
    *,
    request_id: str | None,
    thread_id: str,
    mode: str,
    checkpoint_hit: bool,
    rehydrated: bool,
) -> ContextTrace:
    trace = ContextTrace(
        request_id=request_id,
        thread_hash=hashlib.sha256(thread_id.encode("utf-8")).hexdigest()[:16],
        mode=mode,
        checkpoint_hit=checkpoint_hit,
        rehydrated=rehydrated,
    )
    trace._token = _CURRENT_TRACE.set(trace)
    return trace


def current_context_trace() -> ContextTrace | None:
    return _CURRENT_TRACE.get()


def record_context(
    *,
    purpose: str,
    data_tokens: int,
    recent_tokens: int,
    memory_count: int,
    summary_version: int | None,
) -> None:
    trace = current_context_trace()
    if trace is None:
        return
    trace.node_names.add(purpose)
    trace.input_tokens_by_source["summary_memory"] = max(
        trace.input_tokens_by_source.get("summary_memory", 0), data_tokens
    )
    trace.input_tokens_by_source["recent"] = max(
        trace.input_tokens_by_source.get("recent", 0), recent_tokens
    )
    trace.memory_count = max(trace.memory_count, memory_count)
    if summary_version is not None:
        trace.summary_version = summary_version


def record_retrieval(*, count: int, tokens: int, rejected: int = 0) -> None:
    trace = current_context_trace()
    if trace is None:
        return
    trace.node_names.add("retrieval")
    trace.rag_count = count
    trace.input_tokens_by_source["rag"] = tokens
    if rejected:
        trace.input_tokens_by_source["rag_rejected_chunks"] = rejected


def record_tool_names(names: set[str]) -> None:
    trace = current_context_trace()
    if trace is not None:
        trace.node_names.add("tools")
        trace.tool_names.update(name for name in names if name)


def record_summary(version: int) -> None:
    trace = current_context_trace()
    if trace is not None:
        trace.node_names.add("summary")
        trace.summary_version = version
