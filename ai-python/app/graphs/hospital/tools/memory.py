"""Explicit, confirmed long-term preference memory tools."""

from typing import Annotated, Literal

from langchain.tools import ToolRuntime, tool
from langgraph.types import interrupt
from loguru import logger
from pydantic import Field

from app.graphs.hospital.tools.base import UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.services.java_tool_client import JavaToolClient, JavaToolClientError

MemoryType = Literal[
    "communication_preference", "appointment_preference", "accessibility_need"
]


@tool
def remember_preference(
    memory_type: MemoryType,
    content: Annotated[str, Field(min_length=1, max_length=500)],
    runtime: ToolRuntime[HospitalToolContext],
) -> str:
    """仅当患者明确说“记住”时，保存沟通、挂号或无障碍偏好。不得保存临床事实。"""

    context = runtime.context
    detail = {"type": memory_type, "content": content}
    decision = interrupt({
        "kind": "memory_create",
        "prompt": f"请确认是否长期记住这项偏好：{content}",
        "detail": detail,
    })
    if decision != "approve":
        return "没有保存这项偏好。"
    try:
        JavaToolClient().create_memory(
            context.delegated_token,
            context.request_id,
            memory_type=memory_type,
            content=content,
            source_conversation_id=context.conversation_id or "unknown",
        )
    except JavaToolClientError:
        logger.exception("remember_preference_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE
    return "已保存这项偏好，您随时可以要求我忘掉。"


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
        logger.exception("forget_preference_lookup_failed request_id={}", context.request_id)
        return UNAVAILABLE_MESSAGE
    target = next((item for item in memories if item.memory_id == memory_id), None)
    if target is None:
        return "没有找到这项仍在生效的偏好。"
    decision = interrupt({
        "kind": "memory_delete",
        "prompt": f"请确认是否忘掉这项偏好：{target.content}",
        "detail": {"memoryId": target.memory_id, "type": target.type, "content": target.content},
    })
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
