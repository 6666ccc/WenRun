"""引用与安全校验：核对引用 ID、知识库隔离，以及 excerpt 是否支持事实。"""

import re

from app.graphs.hospital.nodes import ai_message
from app.graphs.hospital.state import State
from app.rag.collections import KnowledgeBase

CITATION_RE = re.compile(r"\[(S\d+)\]")
FACT_TOKEN_RE = re.compile(
    r"(?:\d+(?:\.\d+)?|[零〇一二三四五六七八九十两]+)[点时分秒%％年月日天]"
)
CONSERVATIVE_MARKERS = ("暂无", "没有足够", "不足以", "无法从资料", "建议咨询", "建议以")
OPERATIONAL_MARKERS = ("挂号成功", "已取消挂号", "号源已变化", "没有可挂", "多个可挂号源")
REWRITE_INSTRUCTION = (
    "引用校验未通过：请仅依据已提供的资料重写回答，"
    "删除资料未支持的事实，并为每条事实标注 [S1]、[S2] 等编号。"
)
CONSERVATIVE_ANSWER = (
    "当前检索资料不足以支持该结论。建议以医院官方说明或线下专业人员意见为准，"
    "不要依据未经验证的信息做决定。"
)
_INTENT_KNOWLEDGE_BASE = {
    "hospital": KnowledgeBase.HOSPITAL.value,
    "medical": KnowledgeBase.MEDICAL.value,
}


def citation_validate_node(state: State) -> dict:
    answer = _last_assistant_text(state.get("messages") or [])
    sources = list(state.get("sources") or [])
    intent = state.get("intent")
    retry_count = state.get("retry_count") or 0

    if state.get("error"):
        return {"needs_rewrite": False}
    if _should_skip(intent, answer, sources):
        return {"needs_rewrite": False}

    failures = _collect_failures(answer, sources, intent)
    if not failures:
        return {"needs_rewrite": False}

    if retry_count >= 1:
        return {
            "error": {"code": "UNSUPPORTED_CITATION", "message": CONSERVATIVE_ANSWER},
            "needs_rewrite": False,
            "messages": [ai_message(CONSERVATIVE_ANSWER)],
        }

    return {
        "retry_count": 1,
        "needs_rewrite": True,
        "messages": [ai_message(REWRITE_INSTRUCTION)],
    }


def route_after_citation(state: State) -> str:
    if state.get("needs_rewrite"):
        intent = state.get("intent")
        if intent in {"hospital", "medical"}:
            return intent
    return "save_memory"


def _should_skip(intent, answer: str, sources: list) -> bool:
    if any(marker in (answer or "") for marker in OPERATIONAL_MARKERS):
        return True
    if intent in (None, "chat", "clarify") and not CITATION_RE.search(answer or ""):
        return True
    if intent in {"hospital", "medical"} and not sources and not CITATION_RE.search(answer or ""):
        return True
    return False


def _collect_failures(answer: str, sources: list, intent) -> list[str]:
    failures: list[str] = []
    source_by_id = {_source_id(item): item for item in sources if _source_id(item)}
    cited_ids = CITATION_RE.findall(answer or "")

    if intent in {"hospital", "medical"} and sources and not cited_ids and _looks_like_uncited_fact(answer):
        failures.append("uncited_fact")

    expected_base = _INTENT_KNOWLEDGE_BASE.get(intent) if isinstance(intent, str) else None
    for source_id in cited_ids:
        source = source_by_id.get(source_id)
        if source is None:
            failures.append("missing_id")
            continue
        excerpt = _source_field(source, "excerpt")
        claim = _sentence_for_citation(answer, source_id)
        if not _excerpt_supports(claim, excerpt):
            failures.append("unsupported")
        knowledge_base = _source_field(source, "knowledgeBase") or _source_field(source, "knowledge_base")
        if expected_base and knowledge_base and knowledge_base != expected_base:
            failures.append("wrong_knowledge_base")
    return failures


def _looks_like_uncited_fact(answer: str) -> bool:
    text = (answer or "").strip()
    if not text:
        return False
    return not any(marker in text for marker in CONSERVATIVE_MARKERS)


def _excerpt_supports(claim: str, excerpt: str) -> bool:
    claim_n = _normalize(CITATION_RE.sub("", claim or ""))
    excerpt_n = _normalize(excerpt or "")
    if not claim_n:
        return True
    tokens = FACT_TOKEN_RE.findall(claim_n)
    if tokens:
        return all(token in excerpt_n for token in tokens)
    words = [part for part in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", claim_n)]
    if not words:
        return True
    overlap = sum(1 for word in words if word in excerpt_n)
    return overlap / len(words) >= 0.3


def _sentence_for_citation(answer: str, source_id: str) -> str:
    marker = f"[{source_id}]"
    parts = re.split(r"(?<=[。！？\n])", answer or "")
    for part in parts:
        if marker in part:
            return part
    return answer or ""


def _last_assistant_text(messages) -> str:
    for message in reversed(list(messages)):
        if _is_assistant(message):
            return _message_text(message)
    if messages:
        return _message_text(messages[-1])
    return ""


def _is_assistant(message) -> bool:
    role = _message_role(message).lower()
    return role in {"assistant", "ai"}


def _message_role(message) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or message.get("type") or "")
    return str(getattr(message, "type", None) or getattr(message, "role", "") or "")


def _message_text(message) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _source_id(source) -> str:
    if isinstance(source, dict):
        return str(source.get("id") or "")
    return str(getattr(source, "id", "") or "")


def _source_field(source, name: str):
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")
