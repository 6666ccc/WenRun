"""Pure pending-confirmation selection used by chat resume and safety evaluation."""

from typing import Any

from langgraph.types import Command


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
