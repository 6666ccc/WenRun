"""Pure pending-confirmation selection used by chat resume and safety evaluation."""

import re
from typing import Any, Literal

from langgraph.types import Command

Decision = Literal["approve", "reject"]

# 只收极短、无歧义的口语确认/否决；带条件或追加信息的句子交给旁路聊天，
# 绝不让“确认一下李医生是男的吗”这类句子误提交挂号。
_APPROVE_WORDS = frozenset({
    "好", "好的", "好呀", "好啊", "行", "可以", "可以的", "是", "是的", "对", "对的",
    "确认", "确定", "同意", "没问题", "就这个", "就它", "挂吧", "退吧", "办吧", "ok", "yes",
})
_REJECT_WORDS = frozenset({
    "不", "不用", "不用了", "不要", "不要了", "取消", "算了", "先不", "先不用", "先不要",
    "先不挂", "先不退", "先不办", "不挂", "不挂了", "不退", "不退了", "再想想", "no", "cancel",
})
_FILLER_WORDS = frozenset({"嗯", "谢谢", "谢谢你", "谢谢您", "麻烦了", "吧", "了", "啊", "呀"})
_TRAILING_PARTICLES = ("吧", "了", "啊", "呀", "呢")
_SPLIT_PATTERN = re.compile(r"[,，。.!！~～、;；\s]+")
_MAX_DECISION_LENGTH = 12


def _in_vocabulary(part: str, vocabulary: frozenset[str]) -> bool:
    """中文没有空格分词，允许去掉句尾语气词后再查表（“再想想吧”→“再想想”）。"""

    if part in vocabulary:
        return True
    stripped = part
    while len(stripped) > 1 and stripped.endswith(_TRAILING_PARTICLES):
        stripped = stripped[:-1]
        if stripped in vocabulary:
            return True
    return False


def decision_from_text(text: str) -> Decision | None:
    """把患者在卡片挂起期间输入的自然语言映射成确认决定；无法确定时返回 None。

    每个词都必须落在同一侧词表（或语气填充词）里；混用、带追问或稍长的句子一律不判定。
    """

    normalized = (text or "").strip().lower()
    if not normalized or len(normalized) > _MAX_DECISION_LENGTH:
        return None
    parts = [part for part in _SPLIT_PATTERN.split(normalized) if part]
    if not parts:
        return None

    approve = any(_in_vocabulary(part, _APPROVE_WORDS) for part in parts)
    reject = any(_in_vocabulary(part, _REJECT_WORDS) for part in parts)
    if approve == reject:
        return None
    allowed = (_APPROVE_WORDS if approve else _REJECT_WORDS) | _FILLER_WORDS
    if all(_in_vocabulary(part, allowed) for part in parts):
        return "approve" if approve else "reject"
    return None


def resume_command(
    decision: str,
    interrupt_id: str | None,
    pending: list[dict[str, Any]],
) -> tuple[Command | None, str | None, str | None]:
    """Build LangGraph's interrupt-id map and reject ambiguous or stale resumes."""

    usable = [item for item in pending if item.get("id")]
    if not usable:
        return None, "AI_RESUME_STALE", "没有待确认事项，请重新发起办理"

    target_id = (
        interrupt_id.strip()
        if isinstance(interrupt_id, str) and interrupt_id.strip()
        else None
    )
    if target_id is None:
        if len(usable) == 1:
            target_id = usable[0]["id"]
        else:
            return None, "AI_RESUME_CONFLICT", "请重新发起挂号"

    ids = {item["id"] for item in usable}
    if target_id not in ids:
        return None, "AI_RESUME_STALE", "请重新发起挂号"

    resume_map = {
        item["id"]: (decision if item["id"] == target_id else "reject")
        for item in usable
    }
    return Command(resume=resume_map), None, None
