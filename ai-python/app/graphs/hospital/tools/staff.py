"""医生查询 Tool。对应 Java 的 /api/internal/ai-tools/staff。"""

from langchain.tools import ToolRuntime, tool
from loguru import logger

from app.graphs.hospital.tools.base import MAX_ROWS, UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.graphs.hospital.tools.departments import resolve_department_id
from app.services.java_tool_client import JavaToolClient, JavaToolClientError


def normalize_doctor_name(name: str) -> str:
    """患者常说「张伟医生」，Java 里存的是「张伟」。"""
    text = name.strip()
    for suffix in ("主任医师", "副主任医师", "主治医师", "医师", "医生", "大夫", "主任"):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)].strip()
            break
    return text


def resolve_staff_id(
    client: JavaToolClient, context: HospitalToolContext, name: str
) -> int | None:
    """把患者口中的医生名换成 Java 需要的 staffId。"""
    target = normalize_doctor_name(name)
    if not target:
        return None

    doctors = client.list_staff(context.delegated_token, context.request_id)
    for doctor in doctors:
        if doctor.name == target or doctor.name == name.strip():
            return doctor.id
    for doctor in doctors:
        if target in doctor.name or doctor.name in target:
            return doctor.id
    return None


@tool
def list_doctors(
    runtime: ToolRuntime[HospitalToolContext],
    department: str | None = None,
) -> str:
    """查询本院在岗医生。patient 问某科有哪些医生、有没有某位医生时调用。

    Args:
        department: 科室名，例如「内科」。不填则返回全院在岗医生。
    """
    context = runtime.context
    try:
        client = JavaToolClient()
        dept_id = None
        if department:
            dept_id = resolve_department_id(client, context, department)
            if dept_id is None:
                return f"本院没有查到叫「{department}」的科室，请先确认科室名称。"
        doctors = client.list_staff(
            context.delegated_token,
            context.request_id,
            dept_id=dept_id,
        )
    except JavaToolClientError:
        logger.exception("list_doctors_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE

    if not doctors:
        scope = f"「{department}」" if department else "本院"
        return f"{scope}当前没有查到在岗医生。"

    lines = []
    for doctor in doctors[:MAX_ROWS]:
        parts = [part for part in (doctor.dept_name, doctor.name, doctor.title) if part]
        lines.append("- " + " ".join(parts))
    header = f"「{department}」在岗医生：" if department else "本院在岗医生："
    return header + "\n" + "\n".join(lines)
