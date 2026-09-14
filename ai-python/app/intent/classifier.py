"""CPU 友好的多标签意图分类器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.state import AgentName
from app.intent.rules import normalize_text


@dataclass(frozen=True)
class LightweightPrediction:
    selected_agents: list[AgentName]
    scores: dict[str, float]
    accepted: bool
    margin: float
    nearest_similarity: float
    reason: str | None = None


class LightweightIntentClassifier:
    """字符 n-gram TF-IDF + One-vs-Rest Logistic Regression。

    模型在第一次请求时从随代码版本化的训练集构建。当前数据集很小，启动成本
    可控；后续数据规模扩大时可保持同一接口，改为加载 CI 产出的持久化模型。
    """

    LABELS: tuple[AgentName, ...] = ("knowledge", "chat", "tools")

    def __init__(
        self,
        training_path: Path | None = None,
        *,
        label_threshold: float = 0.50,
        acceptance_threshold: float = 0.60,
        ambiguity_margin: float = 0.12,
        ood_similarity_threshold: float = 0.08,
    ) -> None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.multiclass import OneVsRestClassifier
            from sklearn.preprocessing import MultiLabelBinarizer
        except ImportError as exc:  # pragma: no cover - 仅覆盖部署依赖缺失
            raise RuntimeError("scikit-learn is required for lightweight intent routing") from exc

        path = training_path or Path(__file__).with_name("data") / "training.jsonl"
        self.version = f"tfidf-logreg-{sha256(path.read_bytes()).hexdigest()[:12]}"
        texts, labels = _load_training_data(path)
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=(2, 4),
            min_df=1,
            sublinear_tf=True,
            max_features=12_000,
        )
        matrix = self.vectorizer.fit_transform(texts)
        self.binarizer = MultiLabelBinarizer(classes=list(self.LABELS))
        targets = self.binarizer.fit_transform(labels)
        self.model = OneVsRestClassifier(
            LogisticRegression(
                C=3.0,
                class_weight="balanced",
                max_iter=1_000,
                random_state=42,
            )
        )
        self.model.fit(matrix, targets)
        self.training_matrix = matrix
        self.label_threshold = label_threshold
        self.acceptance_threshold = acceptance_threshold
        self.ambiguity_margin = ambiguity_margin
        self.ood_similarity_threshold = ood_similarity_threshold

    def predict(self, text: str) -> LightweightPrediction:
        from sklearn.metrics.pairwise import cosine_similarity

        normalized = normalize_text(text)
        vector = self.vectorizer.transform([normalized])
        probabilities = self.model.predict_proba(vector)[0]
        scores = {
            str(label): round(float(score), 6)
            for label, score in zip(self.binarizer.classes_, probabilities, strict=True)
        }
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top_score = ranked[0][1]
        margin = top_score - ranked[1][1]
        nearest_similarity = float(cosine_similarity(vector, self.training_matrix).max())
        selected = [
            label for label in self.LABELS if scores[label] >= self.label_threshold
        ]

        reason: str | None = None
        if nearest_similarity < self.ood_similarity_threshold or not selected:
            reason = "out_of_distribution"
        elif top_score < self.acceptance_threshold:
            reason = "low_confidence"
        elif len(selected) == 1 and margin < self.ambiguity_margin:
            reason = "ambiguous_top_intents"

        return LightweightPrediction(
            selected_agents=selected,
            scores=scores,
            accepted=reason is None,
            margin=round(margin, 6),
            nearest_similarity=round(nearest_similarity, 6),
            reason=reason,
        )


def _load_training_data(path: Path) -> tuple[list[str], list[list[str]]]:
    texts: list[str] = []
    labels: list[list[str]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            text = item.get("text")
            item_labels = item.get("labels")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"invalid training text at {path}:{line_number}")
            if not isinstance(item_labels, list):
                raise TypeError(f"invalid training labels at {path}:{line_number}")
            unknown = set(item_labels) - set(LightweightIntentClassifier.LABELS)
            if unknown:
                raise ValueError(f"unknown labels {sorted(unknown)} at {path}:{line_number}")
            texts.append(normalize_text(text))
            labels.append(item_labels)
    if len(texts) < 12:
        raise ValueError("lightweight intent training data is unexpectedly small")
    return texts, labels


@lru_cache(maxsize=1)
def get_lightweight_classifier() -> LightweightIntentClassifier | None:
    """依赖或模型构建失败时关闭本层，让请求安全升级到 LLM。"""

    try:
        settings = get_settings()
        if not settings.intent_lightweight_enabled:
            return None
        return LightweightIntentClassifier(
            label_threshold=settings.intent_label_threshold,
            acceptance_threshold=settings.intent_acceptance_threshold,
            ambiguity_margin=settings.intent_ambiguity_margin,
            ood_similarity_threshold=settings.intent_ood_similarity_threshold,
        )
    except Exception:  # noqa: BLE001 - this optional layer must fail open to the LLM
        logger.exception("Lightweight intent classifier unavailable; escalating to LLM")
        return None
