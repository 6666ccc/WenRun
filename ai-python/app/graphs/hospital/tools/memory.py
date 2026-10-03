"""保存或删除患者长期偏好的写工具。

只有患者明确要求“记住/忘掉”才调用，且两种操作都先用 interrupt()
展示确认卡片；批准后才调用 Java 持久化。临床事实不写成偏好记忆。
"""

import re
from dataclasses import asdict
from datetime import timedelta
from typing import Annotated, Literal

from langchain.tools import ToolRuntime, tool
from langgraph.func import task
from langgraph.runtime import get_runtime
from langgraph.types import interrupt
from loguru import logger
from pydantic import Field

from app.graphs.hospital.tools.base import UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.observability.context_metrics import record_event
from app.services.java_tool_client import JavaToolClient, JavaToolClientError

MemoryType = Literal[
    "communication_preference", "appointment_preference", "accessibility_need"
]

CLINICAL = re.compile(
    r"症状|诊断|处方|过敏|服药|用药|药物|剂量|身高|体重|血压|血糖|心率|BMI|height|weight|\d+\s*(?:kg|公斤|斤|cm|厘米|mg|毫克)",
    re.IGNORECASE,
)


def preference_subject(memory_type: str, content: str) -> str:
    """Only known preference subjects are merged; unrelated same-type items coexist."""
    groups = (
        ("时段", "上午", "下午", "晚上", "早上"),
        ("语言", "中文", "英文", "英语"),
        ("简短", "详细", "简洁", "长篇"),
        ("字体", "大字"),
    )
    for index, words in enumerate(groups):
        if any(word in content for word in words):
            return f"{memory_type}:{index}"
    return f"{memory_type}:{content.strip()}"


@task
def _preference_snapshot(
    memory_type: str, content: str, valid_days: int | None
) -> dict:
    """Checkpoint the displayed version/expiry once, so resume cannot approve a new value."""
    context = get_runtime().context
    items = JavaToolClient().list_memories(context.delegated_token, context.request_id)
    target = next(
        (
            item
            for item in items
            if item.status == "active"
            and preference_subject(item.type, item.content)
            == preference_subject(memory_type, content)
        ),
        None,
    )
    expiry = (
        (context.now + timedelta(days=valid_days))
        .replace(tzinfo=None, microsecond=0)
        .isoformat()
        if valid_days
        else (target.expire_time if target else None)
    )
    return {
        "target": asdict(target) if target else None,
        "expireTime": expiry,
        "content": content,
        "memoryType": memory_type,
        "patientId": context.patient_id,
    }


@tool
def remember_preference(
    memory_type: MemoryType,
    content: Annotated[str, Field(min_length=1, max_length=500)],
    runtime: ToolRuntime[HospitalToolContext],
    valid_days: Annotated[int | None, Field(ge=1, le=365)] = None,
) -> str:
    """仅当患者明确说“记住”时，保存沟通、挂号或无障碍偏好。不得保存临床事实。"""

    context = runtime.context
    if not context.writes_enabled:
        record_event("memoryWrites.create.blocked")
        return "当前会话无法保存偏好，请稍后重试。"
    latest = next(
        (
            str(message.content)
            for message in reversed(runtime.state.get("messages", []))
            if getattr(message, "type", None) == "human"
        ),
        "",
    )
    if not re.search(r"记住|记下|保存.*偏好|更新.*偏好", latest):
        return "只有您明确要求记住时才保存偏好。"
    clauses = re.findall(r"(?:记住|记下)([^。！？\n]*)", latest)
    if CLINICAL.search(content) or any(
        CLINICAL.search(clause) or re.search(r"我吃|服用|吃药|病史", clause)
        for clause in clauses
    ):
        record_event("memoryWrites.create.blocked")
        return "身体数据和病情仅用于当前会话；请到个人档案页更新已有资料。"
    try:
        snapshot = _preference_snapshot(memory_type, content, valid_days).result()
    except JavaToolClientError:
        return UNAVAILABLE_MESSAGE
    target = snapshot["target"]
    detail = {
        "type": memory_type,
        "content": content,
        "patientId": context.patient_id,
        "expireTime": snapshot["expireTime"] or "长期有效",
        "oldContent": target["content"] if target else None,
        "newContent": content,
    }
    # 图先暂停并把卡片送到前端；/resume 批准后才继续执行下方 Java 写入。
    decision = interrupt(
        {
            "kind": "memory_update" if target else "memory_create",
            "prompt": f"请确认是否长期记住这项偏好：{content}",
            "detail": detail,
            "_preference_snapshot": snapshot,
        }
    )
    if isinstance(decision, dict):
        confirmed = decision.get("snapshot")
        if decision.get("decision") == "approve":
            if not isinstance(confirmed, dict) or any(
                [
                    confirmed.get("content") != content,
                    confirmed.get("memoryType") != memory_type,
                    confirmed.get("patientId") != context.patient_id,
                ]
            ):
                return "确认内容已变化，偏好未保存，请重新提出保存请求。"
            snapshot = confirmed
            target = snapshot["target"]
        decision = decision.get("decision")
    if decision != "approve":
        record_event(f"memoryWrites.{'update' if target else 'create'}.rejected")
        return "没有保存这项偏好。"
    try:
        client = JavaToolClient()
        if target:
            client.update_memory(
                context.delegated_token,
                context.request_id,
                memory_id=target["memory_id"],
                memory_type=memory_type,
                content=content,
                expected_version=target["version"],
                expire_time=snapshot["expireTime"],
            )
        else:
            client.create_memory(
                context.delegated_token,
                context.request_id,
                memory_type=memory_type,
                content=content,
                source_conversation_id=context.conversation_id or "unknown",
                expire_time=snapshot["expireTime"],
            )
    except JavaToolClientError as error:
        result = "conflict" if getattr(error, "code", None) == 409 else "blocked"
        record_event(f"memoryWrites.{'update' if target else 'create'}.{result}")
        logger.warning("remember_preference_failed category={}", type(error).__name__)
        return f"偏好未保存：{error}。请重新提出保存请求并确认。"
    record_event(f"memoryWrites.{'update' if target else 'create'}.approved")
    return "已保存这项偏好，可在个人档案页查看和编辑。"


@tool
def forget_preference(
    memory_id: Annotated[str, Field(min_length=1, max_length=64)],
    runtime: ToolRuntime[HospitalToolContext],
) -> str:
    """仅当患者明确要求忘掉时，删除当前患者本人的一条长期偏好。"""

    context = runtime.context
    client = JavaToolClient()
    try:
        memories = client.list_memories(context.delegated_token, context.request_id)
    except JavaToolClientError:
        logger.exception(
            "forget_preference_lookup_failed request_id={}", context.request_id
        )
        return UNAVAILABLE_MESSAGE
    target = next((item for item in memories if item.memory_id == memory_id), None)
    if target is None:
        return "没有找到这项仍在生效的偏好。"
    # 用 Java 查回来的原文展示卡片，避免确认内容只依赖模型生成的 ID。
    decision = interrupt(
        {
            "kind": "memory_delete",
            "prompt": f"请确认是否忘掉这项偏好：{target.content}",
            "detail": {
                "memoryId": target.memory_id,
                "type": target.type,
                "content": target.content,
            },
        }
    )
    if decision != "approve":
        return "保留了这项偏好。"
    try:
        client.delete_memory(
            context.delegated_token, context.request_id, memory_id=target.memory_id
        )
    except JavaToolClientError:
        logger.exception("forget_preference_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE
    return "已忘掉这项偏好。"
