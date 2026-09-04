"""挂号与退号写工具。

提交前一律先 interrupt() 等患者确认，确认卡片上的业务信息全部来自 Java，
不采用模型复述的内容——否则患者确认的和实际提交的可能不是同一张号。
"""

from typing import Any

from langchain.tools import ToolRuntime, tool
from langgraph.types import interrupt
from loguru import logger

from app.graphs.hospital.tools.base import UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.graphs.hospital.tools.schedules import slot_is_expired
from app.services.java_tool_client import (
    JavaToolBusinessError,
    JavaToolClient,
    JavaToolClientError,
)

MAX_IDEMPOTENCY_KEY_LENGTH = 128
REGISTERED_STATUS = 1


def _idempotency_key(context: HospitalToolContext, tool_call_id: str) -> str:
    """患者确认后节点会整段重跑，tool_call_id 不变，所以这个键在重放时保持稳定。"""
    return f"{context.conversation_id or 'na'}:{tool_call_id}"[:MAX_IDEMPOTENCY_KEY_LENGTH]


def _slot_text(detail: dict[str, Any]) -> str:
    parts = [
        detail.get(key)
        for key in ("workDate", "timePeriod", "deptName", "staffName")
        if detail.get(key)
    ]
    return " ".join(str(part) for part in parts)


@tool
def create_registration(schedule_id: int, runtime: ToolRuntime[HospitalToolContext]) -> str:
    """为当前登录患者提交挂号。schedule_id 必须来自 list_schedules 返回的排班，不能猜。"""
    context = runtime.context
    client = JavaToolClient()
    try:
        schedule = client.get_schedule(
            context.delegated_token, context.request_id, schedule_id=schedule_id
        )
    except JavaToolClientError:
        logger.exception(
            "create_registration_schedule_lookup_failed request_id={} schedule_id={}",
            context.request_id,
            schedule_id,
        )
        return UNAVAILABLE_MESSAGE

    if slot_is_expired(schedule.work_date, schedule.time_period, context.now):
        return "这个排班已过期，无法挂号。请重新查询可用号源后再试。"

    if schedule.remaining_count is not None and schedule.remaining_count <= 0:
        return "这个时段的号已约满，请换一个时段。"

    detail = {
        "scheduleId": schedule.id,
        "deptName": schedule.dept_name,
        "staffName": schedule.staff_name,
        "workDate": schedule.work_date,
        "timePeriod": schedule.time_period,
        "remainingCount": schedule.remaining_count,
        "registerFee": schedule.register_fee,
    }
    decision = interrupt(
        {
            "kind": "registration_create",
            "prompt": f"请确认是否为您挂 {_slot_text(detail)} 的号",
            "detail": detail,
        }
    )
    if decision != "approve":
        return "患者取消了本次挂号，没有提交。"

    try:
        client.create_registration(
            context.delegated_token,
            context.request_id,
            schedule_id=schedule_id,
            idempotency_key=_idempotency_key(context, runtime.tool_call_id),
        )
    except JavaToolBusinessError as exc:
        return f"挂号没有成功：{exc}"
    except JavaToolClientError:
        logger.exception(
            "create_registration_failed request_id={} schedule_id={}",
            context.request_id,
            schedule_id,
        )
        return UNAVAILABLE_MESSAGE
    return f"挂号已办好：{_slot_text(detail)}。"


@tool
def cancel_registration(registration_id: int, runtime: ToolRuntime[HospitalToolContext]) -> str:
    """为当前登录患者退号。registration_id 必须来自 list_my_registrations，不能猜。"""
    context = runtime.context
    client = JavaToolClient()
    try:
        registrations = client.list_my_registrations(
            context.delegated_token, context.request_id
        )
    except JavaToolClientError:
        logger.exception(
            "cancel_registration_lookup_failed request_id={} registration_id={}",
            context.request_id,
            registration_id,
        )
        return UNAVAILABLE_MESSAGE

    target = next((item for item in registrations if item.id == registration_id), None)
    if target is None:
        return "没有找到这张挂号单，请先查一下您名下的挂号记录再确认。"
    if target.status != REGISTERED_STATUS:
        return "这张挂号单当前不是已挂号状态，不能退号。"

    detail = {
        "registrationId": target.id,
        "regNo": target.reg_no,
        "deptName": target.dept_name,
        "staffName": target.staff_name,
        "workDate": target.work_date,
        "timePeriod": target.time_period,
        "regFee": target.reg_fee,
    }
    decision = interrupt(
        {
            "kind": "registration_cancel",
            "prompt": f"请确认是否退掉 {_slot_text(detail)} 的号",
            "detail": detail,
        }
    )
    if decision != "approve":
        return "患者取消了本次退号，挂号单保持不变。"

    try:
        client.cancel_registration(
            context.delegated_token, context.request_id, registration_id=registration_id
        )
    except JavaToolBusinessError as exc:
        return f"退号没有成功：{exc}"
    except JavaToolClientError:
        logger.exception(
            "cancel_registration_failed request_id={} registration_id={}",
            context.request_id,
            registration_id,
        )
        return UNAVAILABLE_MESSAGE
    return f"已为您退号：{_slot_text(detail)}。"
