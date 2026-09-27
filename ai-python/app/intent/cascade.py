"""高精度规则之后，按配置运行 Ollama 或保留的 sklearn 本地分类器。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.state import AgentName
from app.intent.classifier import get_lightweight_classifier
from app.intent.ollama_classifier import get_ollama_intent_classifier
from app.intent.rules import detect_safety_flags, match_rules

LocalRouteStage = Literal["rules", "lightweight_model", "ollama_model", "llm_required"]
_CONDITIONAL_REQUEST = re.compile(
    r"如果|要是|假如|假使|倘若|若是|否则|不然|除非|不是的话|要不然|要不就|要不是"
)


@dataclass(frozen=True)
class LocalRouteResult:
    """本地判断的标签、可信度和升级原因，供 begin_node 决定下一步。"""

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
            "router_version": (
                "cascade-v2"
                if self.model_version and self.model_version.startswith("ollama:")
                else "cascade-v1"
            ),
        }


def route_locally(text: str) -> LocalRouteResult:
    """规则优先；本地模型无法确定时，交给 begin_node 的云端 LLM。"""

    safety_flags = detect_safety_flags(text)
    if _CONDITIONAL_REQUEST.search(text):
        return LocalRouteResult(
            accepted=False,
            stage="llm_required",
            safety_flags=safety_flags,
            escalation_reason="conditional_request_requires_reasoning",
        )

    rule_match = match_rules(text)
    if rule_match is not None:
        return LocalRouteResult(
            accepted=True,
            selected_agents=rule_match.selected_agents,
            stage="rules",
            matched_rules=rule_match.matched_rules,
            safety_flags=rule_match.safety_flags,
        )

    if get_settings().intent_local_backend == "ollama":
        return _route_with_ollama(text, safety_flags)
    return _route_with_sklearn(text, safety_flags)


def _route_with_ollama(text: str, safety_flags: list[str]) -> LocalRouteResult:
    version = f"ollama:{get_settings().intent_ollama_model}"
    try:
        prediction = get_ollama_intent_classifier().predict(text)
    except Exception:  # noqa: BLE001 - 本地服务失败时交给云端路由
        logger.exception("Ollama intent classification failed; escalating to cloud LLM")
        return LocalRouteResult(
            accepted=False,
            stage="llm_required",
            safety_flags=safety_flags,
            escalation_reason="ollama_unavailable",
            model_version=version,
        )

    if prediction.accepted:
        disagreement = _ollama_guard_reason(text, prediction.selected_agents)
        if disagreement:
            return LocalRouteResult(
                accepted=False,
                stage="llm_required",
                scores=prediction.scores,
                safety_flags=safety_flags,
                escalation_reason=disagreement,
                margin=prediction.margin,
                model_version=version,
            )
        selected = list(prediction.selected_agents)
        if safety_flags and "knowledge" not in selected:
            selected.insert(0, "knowledge")
        return LocalRouteResult(
            accepted=True,
            selected_agents=selected,
            stage="ollama_model",
            scores=prediction.scores,
            safety_flags=safety_flags,
            margin=prediction.margin,
            model_version=version,
        )

    # 未通过本地质量门槛时不把不可靠标签当成云端失败后的兜底。
    return LocalRouteResult(
        accepted=False,
        stage="llm_required",
        scores=prediction.scores,
        safety_flags=safety_flags,
        escalation_reason=prediction.reason,
        margin=prediction.margin,
        model_version=version,
    )


def _ollama_guard_reason(text: str, selected_agents: list[AgentName]) -> str | None:
    """仅让旧分类器否决明确冲突或域外结果，不用它接管 Ollama。"""

    if not get_settings().intent_ollama_sklearn_guard:
        return None
    classifier = get_lightweight_classifier()
    if classifier is None:
        return None
    try:
        legacy = classifier.predict(text)
    except Exception:  # noqa: BLE001 - 校验器故障不应阻断主路由
        logger.exception("Legacy intent guard failed")
        return None
    if legacy.accepted and set(legacy.selected_agents) != set(selected_agents):
        logger.info(
            "ollama_intent_disagreement ollama_agents={} sklearn_agents={}",
            selected_agents,
            legacy.selected_agents,
        )
        return "local_model_disagreement"
    if legacy.reason == "out_of_distribution":
        return "local_ood_guard"
    return None


def _route_with_sklearn(text: str, safety_flags: list[str]) -> LocalRouteResult:
    """保留旧版 TF-IDF + Logistic Regression 路由，可通过配置切回。"""

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
        selected_agents=list(prediction.selected_agents),
        stage="llm_required",
        scores=prediction.scores,
        safety_flags=safety_flags,
        escalation_reason=prediction.reason,
        margin=prediction.margin,
        nearest_similarity=prediction.nearest_similarity,
        model_version=classifier.version,
    )
