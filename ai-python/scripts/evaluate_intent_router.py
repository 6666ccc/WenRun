"""离线评估规则与轻量模型覆盖率。

用法（在 ai-python 目录）：
    python scripts/evaluate_intent_router.py

被升级到 LLM 的样本不算本地路由错误；本脚本重点检查本地层是否在没有把握时
保持克制，以及所有紧急安全信号是否被召回。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.intent import route_locally


def main() -> int:
    dataset = PROJECT_ROOT / "evals" / "intent_cases.jsonl"
    cases = [
        json.loads(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line
    ]

    stage_counts: Counter[str] = Counter()
    accepted = 0
    accepted_correct = 0
    local_errors: list[dict] = []
    safety_total = 0
    safety_hits = 0

    for case in cases:
        result = route_locally(case["text"])
        stage_counts[result.stage] += 1
        expected = set(case["labels"])
        predicted = set(result.selected_agents)

        if result.accepted:
            accepted += 1
            if predicted == expected:
                accepted_correct += 1
            else:
                local_errors.append(
                    {
                        "text": case["text"],
                        "expected": sorted(expected),
                        "predicted": sorted(predicted),
                        "stage": result.stage,
                    }
                )

        expected_safety = set(case.get("safety_flags") or [])
        if expected_safety:
            safety_total += 1
            if expected_safety.issubset(set(result.safety_flags)):
                safety_hits += 1

    total = len(cases)
    report = {
        "dataset": str(dataset.relative_to(PROJECT_ROOT)),
        "total": total,
        "local_coverage": round(accepted / total, 4),
        "accepted_exact_match_accuracy": (
            round(accepted_correct / accepted, 4) if accepted else 0.0
        ),
        "safety_recall": round(safety_hits / safety_total, 4) if safety_total else None,
        "stage_counts": dict(stage_counts),
        "local_errors": local_errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if local_errors or safety_hits != safety_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
