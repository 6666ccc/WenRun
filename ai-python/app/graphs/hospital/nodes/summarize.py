"""历史摘要节点：在最终回复后压缩旧消息并裁剪 checkpoint。"""

from app.graphs.hospital.memory import needs_summary, split_for_summary
from app.graphs.hospital.state import State
from app.models.chat import model
from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from loguru import logger

SUMMARY_SYSTEM_PROMPT = """你是温润诊所患者端对话的历史压缩器，不对患者说话。
把历史对话压缩成一段中文摘要，供后续轮次当作背景使用。
保留患者自述的症状、持续时间、用药、过敏史，并标明是患者自述；保留关心的科室、医生、日期、时间段、业务事实、未完成事项和偏好。
只压缩已有内容，不补充医学知识，不新增诊断、药名或剂量。不输出 Markdown，控制在 300 字内，直接输出摘要正文。"""


def _build_prompt(existing_summary: str | None, transcript: str) -> list:
    sections = []
    if isinstance(existing_summary, str) and existing_summary.strip():
        sections.append(f"【已有摘要】\n{existing_summary.strip()}")
    sections.append(f"【需要并入摘要的历史对话】\n{transcript}")
    return [SystemMessage(content=SUMMARY_SYSTEM_PROMPT), HumanMessage(content="\n\n".join(sections))]


def _transcript(messages: list) -> str:
    lines = []
    for message in messages:
        speaker = "患者" if getattr(message, "type", "") == "human" else "助手"
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            lines.append(f"{speaker}：{content.strip()}")
    return "\n".join(lines)


def summarize_node(state: State) -> dict:
    if not needs_summary(state):
        return {}
    dropped, kept = split_for_summary(state)
    transcript = _transcript(dropped)
    if not transcript:
        return {}
    try:
        response = model.invoke(_build_prompt(state.get("summary"), transcript))
    except Exception:
        logger.exception("conversation_summary_failed conversation_id={}", state.get("conversation_id"))
        return {}
    content = getattr(response, "content", "")
    summary = content.strip() if isinstance(content, str) else ""
    if not summary:
        return {}
    logger.info(
        "conversation_summarized conversation_id={} dropped={} tokens_before={} tokens_after={}",
        state.get("conversation_id"), len(dropped), count_tokens_approximately(dropped + kept),
        count_tokens_approximately([SystemMessage(content=summary), *kept]),
    )
    return {
        "summary": summary,
        "messages": [RemoveMessage(id=message.id) for message in dropped if getattr(message, "id", None)],
    }
