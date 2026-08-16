from dataclasses import dataclass

from fastapi import Header


@dataclass(frozen=True)
class ToolRuntimeContext:
    delegation_token: str | None


def get_tool_context(
    token: str | None = Header(None, alias="X-Delegated-Token"),
) -> ToolRuntimeContext:
    return ToolRuntimeContext(delegation_token=token)
