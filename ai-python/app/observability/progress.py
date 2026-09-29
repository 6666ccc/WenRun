"""Emit patient-safe lifecycle events; never include prompts or tool arguments."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter, time
from uuid import uuid4

from langgraph.config import get_stream_writer
from langgraph.errors import GraphInterrupt

from app.observability.context_metrics import current_context_trace


LABELS = {
    "route": "了解您的咨询需求",
    "plan": "安排咨询与就诊查询",
    "knowledge": "整理医疗资料与健康建议",
    "chat": "准备咨询答复",
    "business": "核对本院就诊信息",
    "final": "完成答复整理",
    "summary": "记录本轮咨询要点",
    "fast": "准备健康答复",
    "retrieval": "检索院内医疗资料",
    "web": "检索公开医疗资料",
    "departments": "查询本院科室",
    "doctors": "查询本院医生",
    "schedules": "查询出诊安排与剩余号源",
    "registrations": "查询您的预约记录",
}
_PARENT: ContextVar[str | None] = ContextVar("progress_parent", default=None)


def public_progress(data: object) -> dict | None:
    """Explicit whitelist at the SSE boundary; custom graph data is not public."""
    if not isinstance(data, dict) or data.get("type") != "progress":
        return None
    step = data.get("step")
    if not isinstance(step, dict) or step.get("key") not in LABELS:
        return None
    if step.get("status") not in {"running", "completed", "failed", "waiting"}:
        return None
    if not isinstance(step.get("id"), str):
        return None
    safe = {key: step[key] for key in ("id", "key", "status", "parentId", "startedAt", "elapsedMs") if key in step}
    safe["label"] = LABELS[step["key"]]
    return {"type": "status", "content": safe["label"], "step": safe}


@contextmanager
def progress_step(key: str):
    """Time an actual operation, including parallel children and HITL pauses."""
    try:
        writer = get_stream_writer()
    except (RuntimeError, KeyError):
        writer = lambda _event: None
    started = perf_counter()
    trace = current_context_trace()
    step = {
        "id": f"{key}:{uuid4().hex[:10]}", "key": key,
        "label": LABELS[key], "parentId": _PARENT.get(),
        "startedAt": round(time() * 1000), "status": "running", "elapsedMs": 0,
    }
    writer({"type": "progress", "step": dict(step)})
    token = _PARENT.set(step["id"])
    try:
        yield step
    except GraphInterrupt:
        step["status"] = "waiting"
        raise
    except BaseException:
        step["status"] = "failed"
        raise
    finally:
        _PARENT.reset(token)
        if step["status"] == "running":
            step["status"] = "completed"
        step["elapsedMs"] = round((perf_counter() - started) * 1000)
        writer({"type": "progress", "step": dict(step)})
        if trace is not None:
            trace.stage_timings.append({
                "key": key, "status": step["status"], "elapsedMs": step["elapsedMs"],
                "offsetMs": round((started - trace.started_at) * 1000),
            })


def track_operation(key: str):
    """Preserve ToolRuntime annotations and tool schema while observing a tool."""
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            with progress_step(key) as step:
                result = function(*args, **kwargs)
                if isinstance(result, str) and result.startswith("暂时无法查询"):
                    step["status"] = "failed"
                return result
        return run
    return decorate
