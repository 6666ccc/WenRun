"""挂号 HITL：interrupt 暂停，恢复后重新查号源再创建。"""

from langgraph.types import interrupt

from app.graphs.hospital.nodes import ai_message
from app.graphs.hospital.state import State
from app.services.java_tools.models import ToolFailure
from app.services.java_tools.registration import create_registration, idempotency_key


def build_registration_interrupt_node(deps):
    def registration_interrupt(state: State, config=None) -> dict:
        pending = dict(state.get("pending_action") or {})
        interrupt_id = pending.get("interruptId")
        confirmation = interrupt(
            {
                "interruptId": interrupt_id,
                "action": "registration:create",
                "params": pending,
                "summary": pending.get("summary"),
            }
        )
        if not isinstance(confirmation, dict) or not confirmation.get("approved"):
            return {
                "pending_action": None,
                "messages": [ai_message("已取消挂号操作。")],
            }

        token = _delegation_token(config)
        tools = getattr(deps, "tools", None)
        try:
            schedules = _call_tool(tools, "query_schedules", token=token) or []
            schedule_id = pending.get("scheduleId")
            if schedule_id and not _has_schedule(schedules, schedule_id):
                return {
                    "pending_action": None,
                    "error": {"code": "SLOT_SOLD_OUT", "message": "确认期间号源已变化，请重新选择。"},
                    "messages": [ai_message("确认期间号源已变化，请重新选择医生或时段。")],
                }
            payload = {
                "patientId": state.get("patient_id"),
                "scheduleId": schedule_id,
                "idempotencyKey": idempotency_key(state.get("conversation_id") or "", interrupt_id or ""),
                "interruptId": interrupt_id,
            }
            result = _create(tools, token, payload)
        except ToolFailure as failure:
            return {
                "pending_action": None,
                "error": {"code": failure.code, "message": failure.safe_message},
                "messages": [ai_message(failure.safe_message)],
            }
        return {
            "pending_action": None,
            "messages": [ai_message(f"挂号成功，单号 {result.get('id')}")],
        }

    return registration_interrupt


def _create(tools, token, payload):
    if tools is None:
        return {}
    if hasattr(tools, "create_registration"):
        return tools.create_registration(token=token, **payload)
    if getattr(tools, "client", None) is not None:
        return create_registration(tools.client, token, payload)
    return {}


def _call_tool(tools, name: str, **kwargs):
    if tools is None:
        return []
    return getattr(tools, name)(**kwargs)


def _has_schedule(schedules, schedule_id) -> bool:
    if not schedules:
        return False
    for item in schedules:
        if str(item.get("id") or item.get("scheduleId")) == str(schedule_id):
            remaining = item.get("remainingCount")
            return remaining is None or remaining > 0
    return False


def _delegation_token(config) -> str | None:
    if not config:
        return None
    configurable = config.get("configurable") if isinstance(config, dict) else None
    if configurable:
        return configurable.get("delegation_token")
    return None
