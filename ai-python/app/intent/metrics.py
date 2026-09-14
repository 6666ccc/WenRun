"""低基数、线程安全的进程内路由指标。

这些计数用于演示和单实例排障；生产多副本部署时应由 Prometheus/Micrometer
等外部系统聚合，不能把本快照当作全局精确计费数据。
"""

from __future__ import annotations

from collections import Counter
from threading import Lock

_lock = Lock()
_stage_counts: Counter[str] = Counter()
_escalation_counts: Counter[str] = Counter()
_safety_counts: Counter[str] = Counter()
_fallback_count = 0
_out_of_scope_count = 0


def record_route(metadata: dict, *, fallback: bool, out_of_scope: bool) -> None:
    global _fallback_count, _out_of_scope_count

    stage = metadata.get("stage")
    escalation_reason = metadata.get("escalation_reason")
    safety_flags = metadata.get("safety_flags") or []
    with _lock:
        _stage_counts[str(stage or "unknown")] += 1
        if escalation_reason:
            _escalation_counts[str(escalation_reason)] += 1
        for flag in safety_flags:
            _safety_counts[str(flag)] += 1
        if fallback:
            _fallback_count += 1
        if out_of_scope:
            _out_of_scope_count += 1


def route_metrics_snapshot() -> dict:
    with _lock:
        stage_counts = dict(_stage_counts)
        total = sum(_stage_counts.values())
        local = stage_counts.get("rules", 0) + stage_counts.get("lightweight_model", 0)
        return {
            "total": total,
            "localCoverage": round(local / total, 4) if total else 0.0,
            "stageCounts": stage_counts,
            "escalationReasons": dict(_escalation_counts),
            "safetyFlagCounts": dict(_safety_counts),
            "fallbackCount": _fallback_count,
            "outOfScopeCount": _out_of_scope_count,
            "scope": "current_process",
        }


def reset_route_metrics() -> None:
    """测试专用；业务代码不应在运行中清空指标。"""

    global _fallback_count, _out_of_scope_count
    with _lock:
        _stage_counts.clear()
        _escalation_counts.clear()
        _safety_counts.clear()
        _fallback_count = 0
        _out_of_scope_count = 0
