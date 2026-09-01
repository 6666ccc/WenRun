"""科室查询 Tool，以及供其他业务 Tool 复用的科室名解析。"""

from langchain.tools import ToolRuntime, tool
from loguru import logger

from app.graphs.hospital.tools.base import UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.services.java_tool_client import JavaToolClient, JavaToolClientError


def resolve_department_id(
    client: JavaToolClient, context: HospitalToolContext, name: str
) -> int | None:
    """把患者口中的科室名换成 Java 需要的 deptId；模型不接触内部主键。"""
    target = name.strip()
    if not target:
        return None

    departments = client.list_departments(context.delegated_token, context.request_id)
    for department in departments:
        if department.name == target:
            return department.id
    for department in departments:
        if target in department.name or department.name in target:
            return department.id
    return None


@tool
def list_departments(runtime: ToolRuntime[HospitalToolContext]) -> str:
    """查询本院当前开设的科室。患者问有哪些科室、能看哪些科时调用。"""
    context = runtime.context
    try:
        departments = JavaToolClient().list_departments(
            context.delegated_token,
            context.request_id,
        )
    except JavaToolClientError:
        logger.exception("list_departments_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE

    if not departments:
        return "当前没有可展示的科室信息。"
    return "当前可查询的科室：" + "、".join(item.name for item in departments) + "。"
