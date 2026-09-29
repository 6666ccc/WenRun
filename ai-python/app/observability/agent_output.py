"""记录各路由节点的模型/Agent 最终输出，便于按 Agent 定位问题。"""

import json

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.sensitive import redact_sensitive
from app.observability.context_metrics import current_context_trace

_AGENT_LABELS = {
    "intent_router": "云端意图识别模型",
    "jev_intent_classifier": "Jev 意图识别模型",
    "ollama_intent_classifier": "本地 Ollama 意图识别模型",
    "task_planner": "多意图任务规划器",
    "chat_agent": "闲聊助手",
    "knowledge_agent": "医疗知识助手",
    "business_agent": "医院业务助手",
    "fast_agent": "快速问答助手",
    "reply_summarizer": "最终答复汇总器",
    "conversation_summarizer": "会话摘要模型",
}
_PHASE_LABELS = {
    "classification": "意图分类结果",
    "json_repair": "格式修复结果",
    "planning": "任务拆分结果",
    "answer": "回答内容",
    "web_fallback_answer": "联网检索回答",
    "rag_answer": "知识库回答",
    "fallback": "兜底回答",
    "clarification": "澄清问题",
    "urgent_safety": "紧急安全提示",
    "multi_agent_summary": "多助手汇总结果",
    "structured_summary": "会话摘要结果",
    "router_fallback": "路由兜底回答",
}


def _to_text(output: object) -> str:
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, ensure_ascii=False, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(output)


def log_agent_output(agent: str, output: object, *, phase: str = "final") -> None:
    """以结构化单行日志记录输出；屏蔽已识别的 PII 并限制日志长度。"""

    settings = get_settings()
    if not settings.log_agent_outputs:
        return

    text = redact_sensitive(_to_text(output))
    output_chars = len(text)
    max_chars = settings.agent_output_log_max_chars
    truncated = len(text) > max_chars
    if truncated:
        text = f"{text[:max_chars]}…[truncated]"

    trace = current_context_trace()
    payload = {
        "提示": f"{_AGENT_LABELS.get(agent, agent)}｜{_PHASE_LABELS.get(phase, phase)}",
        "event": "agent_output",
        "agent": agent,
        "phase": phase,
        "request_id": trace.request_id if trace else None,
        "thread_hash": trace.thread_hash if trace else None,
        "output_chars": output_chars,
        "truncated": truncated,
    }
    try:
        structured_output = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        structured_output = None

    if structured_output is not None:
        payload["output"] = structured_output
        logger.info(
            "模型/Agent 输出（缩进 JSON）\n{}",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        return

    payload["output_type"] = "text"
    logger.info(
        "模型/Agent 输出信息（JSON）\n{}\n输出正文：\n{}",
        json.dumps(payload, ensure_ascii=False, indent=2),
        text,
    )
