"""会话太长时，压缩旧消息并从检查点中移除它们。

摘要只保存受校验的结构化内容。患者自述仍标为未经验证；
新信息覆盖旧项时，把旧项记录为已失效，避免下一轮继续当成当前事实。
"""

import json
import re
from time import monotonic

from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.runtime import Runtime
from loguru import logger
from pydantic import ValidationError

from app.graphs.hospital.context_builder import bounded_system_message, coerce_summary
from app.graphs.hospital.memory import needs_summary, split_for_summary
from app.graphs.hospital.sensitive import cleaned_memory_text
from app.graphs.hospital.state import ConversationSummary, PatientSelfReport, State
from app.graphs.hospital.tokens import estimate_tokens
from app.graphs.hospital.tools.context import HospitalToolContext, clinic_now
from app.models.chat import model as shared_model
from app.observability.context_metrics import (
    measure_context_operation,
    record_event,
    record_summary,
)
from app.observability.progress import progress_step
from app.services.java_tool_client import JavaToolClient

model = shared_model.model_copy(update={"purpose": "summary"})

SUMMARY_SYSTEM_PROMPT = """你是温润诊所患者端对话的历史压缩器，不对患者说话。
只压缩已有内容，不补充医学知识，不新增诊断、药名或剂量。
患者描述的症状、用药、过敏等只能进入 patient_self_reports，不能当作已验证事实。
不要写入身份证号、手机号、住址、网址或对象存储签名链接，也不要把数据库里的健康档案抄进摘要。
patient_self_reports 的 text 必须摘录患者原文片段，source_message_id 必须来自对应患者消息标注的数据库 ID。
不要摘录助手提及的临床档案数值，也不要把工具结果当作患者自述。不能生成已验证事实或长期偏好。
pending_tasks 表示会话未解决事项，只帮助后续追问，不是事务台账，不能触发业务操作。
逐项提取仍需追问、核对、选择、查询排班等请求；“还要”“尚未”“还需要确认”必须保留对应事项。
一句中的多项请求分别保留；例如“儿科和内科都还要问排班”应产生“查询儿科排班”和“查询内科排班”两项。
涉及身体数据的追问只写待核对的字段，不把助手或工具提供的数值抄入 pending_tasks。
未明确完成或取消的旧事项全部保留。明确完成或取消时，superseded_items 必须复制已有 pending_tasks 中该事项的完整原文，不能换成取消原因或改写。
只输出 JSON，不要 Markdown。字段必须完整：schema_version=2、patient_self_reports、pending_tasks、superseded_items、version。"""

SUMMARY_SYSTEM_PROMPT += """
示例：患者说“儿科和内科都还要查排班，体重测量日期也还需要确认”，正确输出：
{"schema_version":2,"patient_self_reports":[],"pending_tasks":["查询儿科排班","查询内科排班","确认体重测量日期"],"superseded_items":[],"version":1}
示例：已有 pending_tasks=["查询儿科排班","查询内科排班"]，患者明确说内科取消，正确输出：
{"schema_version":2,"patient_self_reports":[],"pending_tasks":["查询儿科排班"],"superseded_items":["查询内科排班"],"version":1}
除患者明确表示全部已完成或不存在任何未解决事项外，不得用空 pending_tasks 忽略上述请求。
"""


def _build_prompt(existing_summary: object, transcript: str) -> list:
    """把已有摘要和待压缩的旧对话一起交给摘要模型。"""
    sections = []
    existing = coerce_summary(existing_summary)
    if existing is not None:
        sections.append(f"【已有结构化摘要】\n{existing.model_dump_json()}")
    sections.append(f"【需要并入摘要的历史对话】\n{transcript}")
    return [
        bounded_system_message(SUMMARY_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(sections)),
    ]


def _transcript(messages: list) -> str:
    """把旧消息整理成带说话人的文字，供摘要模型阅读。"""
    lines = []
    for message in messages:
        speaker = "患者" if getattr(message, "type", "") == "human" else "助手"
        content = (
            getattr(message, "content", "")
            if speaker == "患者"
            else "[非患者资料正文已省略，不能复制临床摘录]"
        )
        if isinstance(content, str) and content.strip():
            db_id = message.additional_kwargs.get("db_id")
            lines.append(f"[source_message_id={db_id}] {speaker}：{content.strip()}")
    return "\n".join(lines)


def _item_key(value: str) -> str:
    """取条目的字段名前缀，用于判断新旧事实是否描述同一件事。"""
    return re.split(r"[:：=]", value, maxsplit=1)[0].strip().lower()


def _merge_items(old: list[str], new: list[str], superseded: list[str]) -> list[str]:
    """按字段名前缀合并新旧条目；值改变时把旧值移到已失效列表。"""
    return list(dict.fromkeys(item for item in [*old, *new] if item not in superseded))


def _merge_reports(
    old: list[PatientSelfReport],
    new: list[PatientSelfReport],
    now_iso: str,
) -> list[PatientSelfReport]:
    """患者自述按原文去重，并给新记录补上收到的时间。"""
    result = list(old)
    seen = {item.text for item in result}
    for item in new:
        if item.text in seen:
            continue
        stamped = (
            item
            if item.reported_at
            else item.model_copy(update={"reported_at": now_iso})
        )
        seen.add(stamped.text)
        result.append(stamped)
    return result


def merge_summary(
    existing_value: object, incoming: ConversationSummary
) -> ConversationSummary:
    """合并模型新摘要与检查点旧摘要，同时保留来源和版本信息。"""
    existing = coerce_summary(existing_value) or ConversationSummary()
    superseded = list(
        dict.fromkeys([*existing.superseded_items, *incoming.superseded_items])
    )
    return ConversationSummary(
        patient_self_reports=_merge_reports(
            existing.patient_self_reports,
            incoming.patient_self_reports,
            clinic_now().isoformat(),
        ),
        pending_tasks=_merge_items(
            existing.pending_tasks, incoming.pending_tasks, superseded
        ),
        superseded_items=list(dict.fromkeys(superseded)),
        version=existing.version + 1,
    )


def _parse_summary(content: object) -> ConversationSummary | None:
    """校验模型给出的 JSON；格式不合格就保留原消息。"""
    if not isinstance(content, str) or not content.strip():
        return None
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        value = json.loads(text)
        required = {
            "schema_version",
            "patient_self_reports",
            "pending_tasks",
            "superseded_items",
            "version",
        }
        if not isinstance(value, dict) or not required.issubset(value):
            return None
        return ConversationSummary.model_validate(value)
    except (ValidationError, ValueError):
        return None


def summarize_node(
    state: State, runtime: Runtime[HospitalToolContext] | None = None
) -> dict:
    """达到长度阈值才压缩；失败时保留原消息，不影响本轮回答。"""
    context = runtime.context if runtime is not None else None
    messages = state.get("messages") or []
    # The latest incoming patient turn is not the previous round's trigger.
    previous = (
        {**state, "messages": messages[:-1]}
        if messages and isinstance(messages[-1], HumanMessage)
        else state
    )
    if not context or not context.execution_id or not needs_summary(previous):
        return {}
    dropped, _ = split_for_summary(state)
    mapped = state.get("message_id_map") or {}
    existing = coerce_summary(state.get("summary"))
    after = existing.last_message_id if existing else 0
    eligible = []
    # Stop at the first unmapped message or oversized batch. Never skip a gap.
    for message in dropped[:200]:
        db_id = message.additional_kwargs.get("db_id") or mapped.get(message.id)
        if not db_id or db_id <= (after or 0):
            break
        candidate = message.model_copy(
            update={"additional_kwargs": {**message.additional_kwargs, "db_id": db_id}}
        )
        if estimate_tokens(_transcript([*eligible, candidate])) > 3_000:
            break
        eligible.append(candidate)
    dropped = eligible
    transcript = _transcript(dropped)
    if not transcript:
        return {}
    record_event("summaryRuns")
    try:
        with progress_step("summary"), measure_context_operation("summaryLatencyMs"):
            response = model.invoke(_build_prompt(state.get("summary"), transcript))
    except Exception:  # noqa: BLE001 - model/provider errors must not break chat
        record_event("summaryFailures")
        logger.warning("conversation_summary_failed")
        return {}
    raw_output = getattr(response, "content", "")
    # Summaries contain health self-reports: never log the model's raw output.
    incoming = _parse_summary(raw_output)
    if incoming is None:
        record_event("summaryFailures")
        logger.warning(
            "conversation_summary_invalid conversation_id={}",
            state.get("conversation_id"),
        )
        return {}
    committing = False
    try:
        sources = {
            message.additional_kwargs["db_id"]: cleaned_memory_text(
                str(message.content)
            )
            or ""
            for message in dropped
            if isinstance(message, HumanMessage)
        }
        for report in incoming.patient_self_reports:
            if (
                report.source_message_id not in sources
                or report.text not in sources[report.source_message_id]
            ):
                raise ValueError("ungrounded self-report")
        summary = merge_summary(state.get("summary"), incoming)
        expected = state.get("durable_summary_version", 0)
        summary = summary.model_copy(
            update={
                "version": expected + 1,
                "last_message_id": dropped[-1].additional_kwargs["db_id"],
            }
        )
        committing = True
        with measure_context_operation("summaryCommitLatencyMs"):
            JavaToolClient().commit_conversation_summary(
                context.delegated_token,
                context.request_id,
                conversation_id=state["conversation_id"],
                execution_id=context.execution_id,
                expected_version=expected,
                covered_ids=[message.additional_kwargs["db_id"] for message in dropped],
                summary=summary.model_dump(),
            )
    except Exception as error:  # noqa: BLE001 - commit failures must retain the original prefix
        record_event("summaryCommitFailures" if committing else "summaryFailures")
        logger.warning("conversation_summary_not_committed")
        if committing and getattr(error, "code", None) == 409:
            return {"requires_recovery": True}
        return {}
    record_event("summaryCommitCount")
    record_summary(summary.version)
    # RemoveMessage 只删已写入摘要的旧消息；未压缩的最近消息仍留在检查点。
    return {
        "summary": summary.model_dump(),
        "durable_summary_version": summary.version,
        "messages": [
            RemoveMessage(id=message.id)
            for message in dropped
            if getattr(message, "id", None)
        ],
    }


def compact_node(state: State, runtime: Runtime[HospitalToolContext]) -> dict:
    """Process consecutive bounded batches before routing, with one ACK per batch."""
    current = dict(state)
    removed = []
    latest = {}
    from app.core.config import get_settings

    deadline = monotonic() + get_settings().recovery_timeout_seconds
    # Operation bound prevents a single request from monopolizing the lock.
    for _ in range(100):
        if monotonic() >= deadline:
            record_event("compactionTimeLimit")
            break
        update = summarize_node(current, runtime)
        if not update:
            break
        if update.get("requires_recovery"):
            return {
                **latest,
                "requires_recovery": True,
                **({"messages": removed} if removed else {}),
            }
        removed.extend(update["messages"])
        ids = {message.id for message in update["messages"]}
        current.update(
            {key: value for key, value in update.items() if key != "messages"}
        )
        current["messages"] = [
            message for message in current["messages"] if message.id not in ids
        ]
        latest = update
    if latest:
        return {**latest, "messages": removed}
    return {}
