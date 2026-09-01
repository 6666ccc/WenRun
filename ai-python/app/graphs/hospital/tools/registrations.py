"""本人挂号记录查询 Tool。患者范围由 Java 依据委托令牌判定，模型无法指定他人。"""

from langchain.tools import ToolRuntime, tool
from loguru import logger

from app.graphs.hospital.tools.base import MAX_ROWS, UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.services.java_tool_client import JavaToolClient, JavaToolClientError, Registration

STATUS_TEXT = {1: "已挂号", 2: "已就诊", 3: "已退号"}


def _format_registration(item: Registration) -> str:
    parts = [part for part in (item.work_date, item.time_period, item.dept_name, item.staff_name) if part]
    line = "- " + " ".join(parts)
    status_text = STATUS_TEXT.get(item.status) if item.status is not None else None
    if status_text:
        line += f"，状态 {status_text}"
    if item.reg_no:
        line += f"，挂号单号 {item.reg_no}"
    return line


@tool
def list_my_registrations(runtime: ToolRuntime[HospitalToolContext]) -> str:
    """查询当前登录患者本人的挂号记录。患者问我挂了什么号、我的预约时调用。"""
    context = runtime.context
    try:
        registrations = JavaToolClient().list_my_registrations(
            context.delegated_token,
            context.request_id,
        )
    except JavaToolClientError:
        logger.exception("list_my_registrations_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE

    if not registrations:
        return "您名下当前没有挂号记录。"
    return "您的挂号记录：\n" + "\n".join(
        _format_registration(item) for item in registrations[:MAX_ROWS]
    )
