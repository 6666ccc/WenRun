"""Compose completed patient-facing answers without another model rewrite."""

import re

SECTION_FIELDS = (("健康建议", "knowledge_reply"), ("就诊安排", "tools_reply"))
_INTERNAL_ID = re.compile(r"[（(]?\s*(?:排班id|挂号单id)\s*=\s*\d+\s*[)）]?|[（(]\s*id\s*=\s*\d+\s*[)）]", re.I)


def uses_reply_sections(state: dict) -> bool:
    """Only a successfully scoped knowledge + business plan can bypass rewriting.

    Other combinations and planner fallback retain the existing final summarizer.
    """
    if set(state.get("selected_agents") or []) != {"knowledge", "tools"}:
        return False
    plan = state.get("task_plan") or {}
    tasks = plan.get("tasks") or []
    return {task.get("agent") for task in tasks if isinstance(task, dict) and task.get("goal")} == {"knowledge", "tools"}


def compose_reply_sections(state: dict, *, ready_prefix: bool = False) -> str:
    blocks = []
    for label, field in SECTION_FIELDS:
        reply = state.get(field)
        if not isinstance(reply, str) or not reply.strip():
            if ready_prefix:
                break
            continue
        # Apply the same internal-ID exclusion as the patient UI, also to stored text.
        reply = _INTERNAL_ID.sub("", reply).strip()
        blocks.append(f"### {label}\n\n{reply}")
    return "\n\n".join(blocks)
