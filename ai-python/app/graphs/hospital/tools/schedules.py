"""排班与余号查询 Tool。对应 Java 的 /api/internal/ai-tools/schedules。"""

from datetime import date, time, timedelta

from langchain.tools import ToolRuntime, tool
from loguru import logger

from app.graphs.hospital.tools.base import MAX_ROWS, UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.graphs.hospital.tools.departments import resolve_department_id
from app.graphs.hospital.tools.staff import resolve_staff_id
from app.services.java_tool_client import JavaToolClient, JavaToolClientError, Schedule

RELATIVE_DAYS = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2}
# 与 Java ScheduleCutoffs.defaults() / wenrun.clinic.*-end 默认值对齐。
PERIOD_ENDS = {"上午": time(12, 0), "下午": time(18, 0), "晚上": time(21, 0)}


def clinic_today(now) -> date:
    return now.astimezone(CLINIC_TZ).date() if now.tzinfo else now.date()


def resolve_work_date(value: str, today: date) -> date | None:
    """支持「今天/明天/后天」与 YYYY-MM-DD；无法识别时返回 None 由调用方提示。"""
    text = value.strip()
    if text in RELATIVE_DAYS:
        return today + timedelta(days=RELATIVE_DAYS[text])
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def slot_is_expired(work_date: str | None, time_period: str | None, now) -> bool:
    """与 Java ScheduleExpiry 一致：过去的就诊日，或当天已过对应时段截止时刻。"""
    if not work_date:
        return False
    try:
        work = date.fromisoformat(str(work_date)[:10])
    except ValueError:
        return False
    today = clinic_today(now)
    if work < today:
        return True
    if work > today:
        return False
    end = PERIOD_ENDS.get(time_period or "")
    if end is None:
        return False
    local = now.astimezone(CLINIC_TZ) if getattr(now, "tzinfo", None) else now
    return local.time() >= end


def _format_schedule(item: Schedule) -> str:
    parts = [part for part in (item.work_date, item.time_period, item.dept_name, item.staff_name) if part]
    prefix = f"排班id={item.id} " if item.id is not None else ""
    line = "- " + prefix + " ".join(parts)
    if item.remaining_count is not None:
        line += f"，余号 {item.remaining_count}"
        if item.total_count is not None:
            line += f"/{item.total_count}"
    if item.register_fee is not None:
        line += f"，挂号费 {item.register_fee}"
    return line


@tool
def list_schedules(
    runtime: ToolRuntime[HospitalToolContext],
    department: str | None = None,
    doctor: str | None = None,
    work_date: str | None = None,
) -> str:
    """查询排班与余号。患者问某科某天有没有号、某位医生何时出诊时调用。

    Args:
        department: 科室名，例如「内科」。不填则不按科室过滤。
        doctor: 医生姓名，例如「张伟」或「张伟医生」。不填则不按医生过滤。
        work_date: 就诊日期，可写「今天」「明天」「后天」或 YYYY-MM-DD。不填则返回今天及以后的排班。
    """
    context = runtime.context

    target_date = None
    if work_date:
        target_date = resolve_work_date(work_date, clinic_today(context.now))
        if target_date is None:
            return "没看懂就诊日期，请说「今天」「明天」或具体到某年某月某日。"

    try:
        client = JavaToolClient()
        dept_id = None
        if department:
            dept_id = resolve_department_id(client, context, department)
            if dept_id is None:
                return f"本院没有查到叫「{department}」的科室，请先确认科室名称。"
        staff_id = None
        if doctor:
            staff_id = resolve_staff_id(client, context, doctor)
            if staff_id is None:
                return f"本院没有查到叫「{doctor}」的医生，请先确认姓名。"
        schedules = client.list_schedules(
            context.delegated_token,
            context.request_id,
            dept_id=dept_id,
            work_date=target_date,
            staff_id=staff_id,
        )
    except JavaToolClientError:
        logger.exception("list_schedules_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE

    if not schedules:
        return "这个条件下没有查到排班，可以换个科室、医生或日期再看看。"
    return "查询到的排班：\n" + "\n".join(_format_schedule(item) for item in schedules[:MAX_ROWS])
