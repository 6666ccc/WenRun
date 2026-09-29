"""记录每轮对话的耗时、上下文长度和工具名，供排查性能问题。

这里只记录数量和类别，不记录患者原话、工具参数、令牌或完整会话号。
thread_hash 是会话号的短哈希，用来关联日志而不直接暴露标识。
"""

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
    """单轮请求的统计暂存区；SSE 流结束时调用 finish() 汇总一次。"""

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
    stage_timings: list[dict] = field(default_factory=list)
    _token: Token | None = field(default=None, repr=False)
    _finished: bool = field(default=False, repr=False)

    def finish(self, *, error_code: str | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        if error_code:
            self.error_code = error_code
        node_labels = {
            "route": "意图识别",
            "plan": "任务规划",
            "chat": "闲聊回答",
            "knowledge": "医疗知识回答",
            "tools": "医院业务处理",
            "retrieval": "知识检索",
            "final": "最终答复汇总",
            "summarize": "会话摘要",
            "fast": "快速问答",
        }
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
            "stage_timings": list(self.stage_timings),
        }
        logger.info(
            "本轮请求统计 请求模式={} 执行节点={} 首个文字耗时={} 毫秒 总耗时={} 毫秒 检索片段数={} 错误代码={} | context_trace",
            {"normal": "普通模式", "fast": "快速模式"}.get(self.mode, self.mode),
            [f"{node_labels.get(node, node)}（{node}）" for node in payload["node_names"]],
            payload["first_token_ms"],
            payload["total_ms"],
            payload["rag_count"],
            payload["error_code"],
        )
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
_RECENT_REQUESTS: deque[dict] = deque(maxlen=20)


def _record_snapshot(payload: dict) -> None:
    """把本轮统计合并到进程内计数器，供指标接口读取。"""
    global _COMPLETED
    with _METRICS_LOCK:
        _COMPLETED += 1
        _RECENT_REQUESTS.append({
            key: payload.get(key) for key in
            ("request_id", "mode", "first_token_ms", "total_ms", "error_code", "stage_timings")
        })
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
    """计算最近样本的第 95 百分位耗时。"""
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
            "recentRequests": list(_RECENT_REQUESTS),
        }


def begin_context_trace(
    *,
    request_id: str | None,
    thread_id: str,
    mode: str,
    checkpoint_hit: bool,
    rehydrated: bool,
) -> ContextTrace:
    """开始记录本轮对话，并绑定到当前异步请求。"""
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
    """读取当前请求正在累计的统计对象。"""
    return _CURRENT_TRACE.get()


def record_context(
    *,
    purpose: str,
    data_tokens: int,
    recent_tokens: int,
    memory_count: int,
    summary_version: int | None,
) -> None:
    """记录送入模型的摘要、最近消息用量及实际选中的偏好条数。"""
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
    """记录院内检索片段数量和长度，不记录片段正文。"""
    trace = current_context_trace()
    if trace is None:
        return
    trace.node_names.add("retrieval")
    trace.rag_count = count
    trace.input_tokens_by_source["rag"] = tokens
    if rejected:
        trace.input_tokens_by_source["rag_rejected_chunks"] = rejected


def record_tool_names(names: set[str]) -> None:
    """只记录被调用的工具名称，不记录参数或返回内容。"""
    trace = current_context_trace()
    if trace is not None:
        trace.node_names.add("tools")
        trace.tool_names.update(name for name in names if name)


def record_summary(version: int) -> None:
    """记下本轮生成的会话摘要版本号。"""
    trace = current_context_trace()
    if trace is not None:
        trace.node_names.add("summary")
        trace.summary_version = version
