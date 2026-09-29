"""Jev 与 Ollama 共用的分类结果；标签不确定时由级联路由升级。"""

from dataclasses import dataclass

from app.graphs.hospital.state import AgentName

LABELS: tuple[AgentName, ...] = ("knowledge", "chat", "tools")


@dataclass(frozen=True)
class IntentPrediction:
    selected_agents: list[AgentName]
    scores: dict[str, float]
    accepted: bool
    margin: float | None
    reason: str | None = None
