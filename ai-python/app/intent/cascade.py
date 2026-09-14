"""规则与轻量模型组成的本地级联路由。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.graphs.hospital.state import AgentName
from app.intent.classifier import get_lightweight_classifier
from app.intent.rules import detect_safety_flags, match_rules

LocalRouteStage = Literal["rules", "lightweight_model", "llm_required"]


@dataclass(frozen=True)
class LocalRouteResult:
    accepted: bool
    selected_agents: list[AgentName] = field(default_factory=list)
    stage: LocalRouteStage = "llm_required"
    scores: dict[str, float] = field(default_factory=dict)
    matched_rules: list[str] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    escalation_reason: str | None = None
    margin: float | None = None
    nearest_similarity: float | None = None
    model_version: str | None = None

    def metadata(self) -> dict:
        return {
            "stage": self.stage,
            "scores": self.scores,
            "matched_rules": self.matched_rules,
            "safety_flags": self.safety_flags,
            "escalation_reason": self.escalation_reason,
            "margin": self.margin,
            "nearest_similarity": self.nearest_similarity,
            "model_version": self.model_version,
            "router_version": "cascade-v1",
        }


def route_locally(text: str) -> LocalRouteResult:
    """依次尝试高精度规则和轻量模型；不确定时明确请求 LLM。"""

    safety_flags = detect_safety_flags(text)
    rule_match = match_rules(text)
    if rule_match is not None:
        return LocalRouteResult(
            accepted=True,
            selected_agents=rule_match.selected_agents,
            stage="rules",
            matched_rules=rule_match.matched_rules,
            safety_flags=rule_match.safety_flags,
        )

    classifier = get_lightweight_classifier()
    if classifier is None:
        return LocalRouteResult(
            accepted=False,
            stage="llm_required",
            safety_flags=safety_flags,
            escalation_reason="lightweight_model_unavailable",
        )

    prediction = classifier.predict(text)
    if prediction.accepted:
        selected = list(prediction.selected_agents)
        if safety_flags and "knowledge" not in selected:
            selected.insert(0, "knowledge")
        return LocalRouteResult(
            accepted=True,
            selected_agents=selected,
            stage="lightweight_model",
            scores=prediction.scores,
            safety_flags=safety_flags,
            margin=prediction.margin,
            nearest_similarity=prediction.nearest_similarity,
            model_version=classifier.version,
        )

    return LocalRouteResult(
        accepted=False,
        stage="llm_required",
        scores=prediction.scores,
        safety_flags=safety_flags,
        escalation_reason=prediction.reason,
        margin=prediction.margin,
        nearest_similarity=prediction.nearest_similarity,
        model_version=classifier.version,
    )
