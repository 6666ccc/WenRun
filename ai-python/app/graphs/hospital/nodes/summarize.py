"""会话太长时，压缩旧消息并从检查点中移除它们。

摘要只保存受校验的结构化内容。患者自述仍标为未经验证；
新信息覆盖旧项时，把旧项记录为已失效，避免下一轮继续当成当前事实。
"""

import re

from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from loguru import logger
from pydantic import ValidationError

from app.graphs.hospital.context_builder import bounded_system_message, coerce_summary
from app.graphs.hospital.memory import needs_summary, split_for_summary
from app.graphs.hospital.state import ConversationSummary, PatientSelfReport, State
from app.graphs.hospital.tools.context import clinic_now
from app.models.chat import model
from app.observability.agent_output import log_agent_output
from app.observability.context_metrics import record_summary
from app.observability.progress import progress_step

SUMMARY_SYSTEM_PROMPT = """你是温润诊所患者端对话的历史压缩器，不对患者说话。
只压缩已有内容，不补充医学知识，不新增诊断、药名或剂量。
患者描述的症状、用药、过敏等只能进入 patient_self_reports，不能当作已验证事实。
不要写入身份证号、手机号、住址、网址或对象存储签名链接，也不要把数据库里的健康档案抄进摘要。
医院工具明确返回的业务结果才可进入 verified_business_facts。
新内容推翻旧内容时，把旧项移入 superseded_items，不得同时当作当前事实。
只输出 JSON，不要 Markdown。字段必须完整：patient_self_reports、preferences、verified_business_facts、pending_tasks、superseded_items、version。"""


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
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            lines.append(f"{speaker}：{content.strip()}")
    return "\n".join(lines)


def _item_key(value: str) -> str:
    """取条目的字段名前缀，用于判断新旧事实是否描述同一件事。"""
    return re.split(r"[:：=]", value, maxsplit=1)[0].strip().lower()


def _merge_items(old: list[str], new: list[str], superseded: list[str]) -> list[str]:
    """按字段名前缀合并新旧条目；值改变时把旧值移到已失效列表。"""
    result = list(old)
    positions = {_item_key(item): index for index, item in enumerate(result)}
    for item in new:
        key = _item_key(item)
        index = positions.get(key)
        if index is None:
            positions[key] = len(result)
            result.append(item)
        elif result[index] != item:
            superseded.append(result[index])
            result[index] = item
    return result[-20:]


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
        stamped = item if item.reported_at else item.model_copy(update={"reported_at": now_iso})
        seen.add(stamped.text)
        result.append(stamped)
    return result[-20:]


def merge_summary(existing_value: object, incoming: ConversationSummary) -> ConversationSummary:
    """合并模型新摘要与检查点旧摘要，同时保留来源和版本信息。"""
    existing = coerce_summary(existing_value) or ConversationSummary()
    superseded = list(dict.fromkeys([*existing.superseded_items, *incoming.superseded_items]))
    return ConversationSummary(
        patient_self_reports=_merge_reports(
            existing.patient_self_reports,
            incoming.patient_self_reports,
            clinic_now().isoformat(),
        ),
        preferences=_merge_items(existing.preferences, incoming.preferences, superseded),
        verified_business_facts=_merge_items(
            existing.verified_business_facts, incoming.verified_business_facts, superseded
        ),
        pending_tasks=_merge_items(existing.pending_tasks, incoming.pending_tasks, superseded),
        superseded_items=list(dict.fromkeys(superseded))[-30:],
        version=max(existing.version, incoming.version) + 1,
    )


def _parse_summary(content: object) -> ConversationSummary | None:
    """校验模型给出的 JSON；格式不合格就保留原消息。"""
    if not isinstance(content, str) or not content.strip():
        return None
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        return ConversationSummary.model_validate_json(text)
    except ValidationError:
        return None


def summarize_node(state: State) -> dict:
    """达到长度阈值才压缩；失败时保留原消息，不影响本轮回答。"""
    if not needs_summary(state):
        return {}
    dropped, kept = split_for_summary(state)
    transcript = _transcript(dropped)
    if not transcript:
        return {}
    try:
        with progress_step("summary"):
            response = model.invoke(_build_prompt(state.get("summary"), transcript))
    except Exception:  # noqa: BLE001 - model/provider errors must not break chat
        logger.exception("conversation_summary_failed conversation_id={}", state.get("conversation_id"))
        return {}
    raw_output = getattr(response, "content", "")
    log_agent_output("conversation_summarizer", raw_output, phase="structured_summary")
    incoming = _parse_summary(raw_output)
    if incoming is None:
        logger.warning(
            "conversation_summary_invalid conversation_id={}", state.get("conversation_id")
        )
        return {}
    summary = merge_summary(state.get("summary"), incoming)
    logger.info(
        "conversation_summarized conversation_id={} dropped={} tokens_before={} tokens_after={}",
        state.get("conversation_id"), len(dropped), count_tokens_approximately(dropped + kept),
        count_tokens_approximately([SystemMessage(content=summary.model_dump_json()), *kept]),
    )
    record_summary(summary.version)
    # RemoveMessage 只删已写入摘要的旧消息；未压缩的最近消息仍留在检查点。
    return {
        "summary": summary.model_dump(),
        "messages": [RemoveMessage(id=message.id) for message in dropped if getattr(message, "id", None)],
    }
