"""医院个性化节点：组合医院 RAG 与受控 Java 查询 Tool。"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from app.core.config import get_settings
from app.graphs.hospital.nodes import ai_message, invoke_reply_agent
from app.graphs.hospital.nodes.hospital_query import (
    extract_hospital_query,
    format_slot_choices,
    match_dept_id,
    select_slot,
)
from app.graphs.hospital.nodes.retrieval import last_user_text, retrieve_for_node
from app.graphs.hospital.state import State
from app.rag.collections import KnowledgeBase
from app.rag.rag import chunks_to_sources, format_source_context
from app.services.java_tools.models import ToolFailure

if TYPE_CHECKING:
    from app.graphs.hospital.graph import GraphDependencies

ALLOWED_STEPS = (
    "hospital_rag",
    "query_depts",
    "query_doctors",
    "query_schedules",
    "prepare_registration",
)


def plan_hospital_steps(text: str, tools) -> list[str]:
    if tools is None:
        return ["hospital_rag"]
    query = extract_hospital_query(text)
    steps: list[str] = []
    if any(token in text for token in ("哪里", "位置", "怎么走", "在哪")) or not any(
        token in text for token in ("挂", "挂号", "号源", "排班", "医生", "大夫", "科室")
    ):
        steps.append("hospital_rag")
    if "科室" in text or query.get("dept_name"):
        steps.append("query_depts")
    if any(token in text for token in ("医生", "大夫")):
        steps.append("query_doctors")
    if any(token in text for token in ("号源", "排班", "下午", "上午", "明天", "今天", "后天")):
        steps.append("query_schedules")
    if any(token in text for token in ("挂", "挂号")):
        if "query_schedules" not in steps:
            steps.append("query_schedules")
        steps.append("prepare_registration")
    if not steps:
        steps.append("hospital_rag")
    max_steps = 8
    try:
        max_steps = get_settings().agent_max_steps
    except Exception:
        pass
    return [step for step in steps if step in ALLOWED_STEPS][:max_steps]


def route_after_hospital(state: State) -> str:
    if state.get("pending_action"):
        return "registration_interrupt"
    return "citation_validate"


def build_hospital_node(deps: "GraphDependencies"):
    def hospital(state: State, config=None) -> dict:
        query_text = last_user_text(state)
        parsed = extract_hospital_query(query_text)
        steps = plan_hospital_steps(query_text, getattr(deps, "tools", None))
        sources: list[dict] = list(state.get("sources") or [])
        observations: list[str] = []
        pending_action = None
        token = _delegation_token(config)
        schedules = []
        depts = []
        dept_id = None

        try:
            if "hospital_rag" in steps:
                chunks = retrieve_for_node(deps.hospital_retriever, KnowledgeBase.HOSPITAL, state)
                rag_sources = chunks_to_sources(chunks, KnowledgeBase.HOSPITAL)
                for item in rag_sources:
                    item["kind"] = "rag"
                sources.extend(rag_sources)
                if rag_sources:
                    observations.append(format_source_context(rag_sources))

            if getattr(deps, "tools", None) and ("query_depts" in steps or parsed.get("dept_name")):
                depts = _call_tool(deps.tools, "query_depts", token=token) or []
                sources.append(_tool_source("query_depts", depts))
                observations.append(f"科室查询结果：{depts}")
                dept_id = match_dept_id(depts, parsed.get("dept_name"))

            if "query_doctors" in steps:
                rows = _call_tool(deps.tools, "query_doctors", token=token, dept_id=dept_id)
                sources.append(_tool_source("query_doctors", rows))
                observations.append(f"医生查询结果：{rows}")

            if "query_schedules" in steps:
                schedules = _call_tool(
                    deps.tools,
                    "query_schedules",
                    token=token,
                    dept_id=dept_id,
                    work_date=parsed.get("work_date"),
                ) or []
                sources.append(_tool_source("query_schedules", schedules))
                observations.append(f"排班查询结果：{schedules}")

            if "prepare_registration" in steps:
                slot, filtered = select_slot(schedules, parsed)
                if not filtered:
                    return _node_update(
                        "当前没有可挂的号源，请换一个科室或时段。",
                        sources,
                        steps,
                    )
                if slot is None:
                    return _node_update(format_slot_choices(filtered), sources, steps)
                interrupt_id = str(uuid4())
                pending_action = {
                    "interruptId": interrupt_id,
                    "action": "registration:create",
                    "scheduleId": slot.get("id") or slot.get("scheduleId"),
                    "patientId": state.get("patient_id"),
                    "summary": _registration_summary(state, slot),
                    "slot": slot,
                }
        except ToolFailure as failure:
            return {
                "error": {"code": failure.code, "message": failure.safe_message},
                "messages": [ai_message(failure.safe_message)],
                "sources": sources,
                "pending_action": None,
                "needs_rewrite": False,
            }

        agent_state = state
        if observations:
            messages = list(state.get("messages") or [])
            messages.append({"role": "system", "content": "\n".join(observations)})
            agent_state = {**state, "messages": messages}
        reply = invoke_reply_agent(deps.hospital_agent, agent_state)
        if pending_action:
            reply = pending_action["summary"]
        return _node_update(reply, sources, steps, pending_action)

    return hospital


def _node_update(reply: str, sources: list, steps: list[str], pending_action=None) -> dict:
    update = {
        "messages": [ai_message(reply)],
        "needs_rewrite": False,
        "task_plan": [{"step": step} for step in steps],
        "pending_action": pending_action,
    }
    if sources:
        update["sources"] = sources
    return update


def _call_tool(tools, name: str, **kwargs):
    if tools is None:
        return []
    method = getattr(tools, name)
    return method(**kwargs)


def _delegation_token(config) -> str | None:
    if not config:
        return None
    configurable = config.get("configurable") if isinstance(config, dict) else None
    if configurable:
        return configurable.get("delegation_token")
    return None


def _tool_source(tool_name: str, payload) -> dict:
    return {
        "kind": "tool",
        "id": f"T-{tool_name}",
        "toolName": tool_name,
        "queryTime": datetime.now(timezone.utc).isoformat(),
        "summary": str(payload)[:300],
        "excerpt": str(payload)[:300],
    }


def _registration_summary(state: State, slot: dict) -> str:
    return (
        f"请确认挂号：患者{state.get('patient_id')}，"
        f"{slot.get('deptName') or '科室未指定'} "
        f"{slot.get('staffName') or '医生未指定'}，"
        f"{slot.get('workDate')} {slot.get('timePeriod')}，"
        f"费用{slot.get('registerFee')}。"
    )
