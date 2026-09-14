"""医院业务 Tool 的运行时上下文。仅在单次请求内有效，禁止写入持久化 checkpoint。"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# 中国无夏令时，固定 UTC+8。不用 ZoneInfo("Asia/Shanghai")，避免 Windows 缺 tzdata 时 import 失败。
CLINIC_TZ = timezone(timedelta(hours=8), name="CST")
WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def clinic_now() -> datetime:
    """本次请求的北京时间，来自操作系统时钟。"""
    return datetime.now(CLINIC_TZ)


def format_clinic_clock(now: datetime) -> str:
    local = now.astimezone(CLINIC_TZ)
    weekday = WEEKDAYS[local.weekday()]
    return f"{local:%Y-%m-%d} {weekday} {local:%H:%M}（北京时间）"


@dataclass(frozen=True)
class HospitalToolContext:
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
