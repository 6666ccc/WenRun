"""工具调用需要的请求级资料：委托身份、追踪号、时间和写能力开关。

它只随当前 HTTP 请求传给节点，不进入可持久化的 State 或检查点。
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock

# 中国无夏令时，固定 UTC+8。不用 ZoneInfo("Asia/Shanghai")，避免 Windows 缺 tzdata 时 import 失败。
CLINIC_TZ = timezone(timedelta(hours=8), name="CST")
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def clinic_now() -> datetime:
    """本次请求的北京时间，来自操作系统时钟。"""
    return datetime.now(CLINIC_TZ)


def format_clinic_clock(now: datetime) -> str:
    """把时间写成模型容易理解的北京时间与星期。"""
    local = now.astimezone(CLINIC_TZ)
    weekday = WEEKDAYS[local.weekday()]
    return f"{local:%Y-%m-%d} {weekday} {local:%H:%M}（北京时间）"


@dataclass(frozen=True)
class HospitalToolContext:
    """一次请求的可信运行环境，工具从这里取令牌而不是让模型编造身份。"""

    delegated_token: str
    request_id: str | None = None
    user_id: int | None = None
    patient_id: int | None = None
    now: datetime = field(default_factory=clinic_now)
    #: 幂等键的前缀来源。与 checkpointer 的 thread_id 相同。
    conversation_id: str | None = None
    #: 只有会话带 checkpointer 且不是快速模式时才为 True。为 False 时不挂载写工具，
    #: 否则 interrupt() 会静默失效：工具不执行，final_reply 为空，整轮对话变成 500。
    writes_enabled: bool = False
    execution_id: str | None = None
    #: 本轮已读的临床字段集合；多次工具调用也不能无限扩大档案读取范围。
    clinical_scopes_read: set[str] = field(
        default_factory=set, compare=False, repr=False
    )
    clinical_read_lock: Lock = field(default_factory=Lock, compare=False, repr=False)
