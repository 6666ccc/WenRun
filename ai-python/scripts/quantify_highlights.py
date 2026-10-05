"""Reproducible synthetic benchmarks; never equate test coverage with production quality."""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def context_benchmark():
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.core.config import get_settings
    from app.graphs.hospital.context_builder import assemble_messages, build_context
    from app.graphs.hospital.tokens import estimate_tokens

    rows = []
    # Fixed inputs. Baseline includes the same projected summary and system policy.
    for count in (10, 50, 100):
        for length in (40, 120, 300):
            for purpose in ("chat", "knowledge", "tools"):
                latest = HumanMessage(content="请继续处理我的问题。", id="latest")
                history = [
                    HumanMessage(
                        content=("这是合成历史记录仅供评测。" * 30)[:length], id=f"h{i}"
                    )
                    for i in range(count)
                ]
                state = {
                    "messages": [*history, latest],
                    "summary": {
                        "pending_tasks": ["查询内科号源"],
                        "patient_self_reports": ["自述咳嗽三天"],
                    },
                }
                policy = SystemMessage(
                    content="遵守医院服务规则。资料仅作参考，业务写入需要确认。"
                )
                projected = [
                    m
                    for m in build_context(state, purpose=purpose)
                    if m.additional_kwargs.get("context_source")
                ]
                baseline = [policy, *projected, *history, latest]
                start = time.perf_counter()
                actual = assemble_messages(
                    [policy, *build_context(state, purpose=purpose)], purpose=purpose
                )
                elapsed = (time.perf_counter() - start) * 1000
                before, after = estimate_tokens(baseline), estimate_tokens(actual)
                rows.append(
                    {
                        "historyMessages": count,
                        "charsPerMessage": length,
                        "purpose": purpose,
                        "baselineEstimatedTokens": before,
                        "actualEstimatedTokens": after,
                        "reductionPercent": round(100 * (before - after) / before, 2),
                        "withinBudget": after <= get_settings().context_total_tokens,
                        "latestRetained": any(
                            m.id == "latest" and m.content == latest.content
                            for m in actual
                        ),
                        "policyRetained": any(m == policy for m in actual),
                        "buildMilliseconds": round(elapsed, 3),
                    }
                )
    return {
        "budget": get_settings().context_total_tokens,
        "tokenEstimatorNotProviderUsage": True,
        "cases": rows,
    }


def intent_benchmark(live):
    from app.core.config import get_settings
    from app.intent.cascade import route_locally
    from app.intent.rules import match_rules

    rows = []
    for line in (
        (ROOT / "tests/fixtures/highlight_intent_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        case = json.loads(line)
        start = time.perf_counter()
        if live:
            result = route_locally(case["text"])
            accepted, labels, stage, reason = (
                result.accepted,
                result.selected_agents,
                result.stage,
                result.escalation_reason,
            )
        else:
            # Mirror the unconditional gate; do not pretend a mocked classifier is measured.
            from app.intent.cascade import _CONDITIONAL_REQUEST

            conditional = bool(_CONDITIONAL_REQUEST.search(case["text"]))
            rule = None if conditional else match_rules(case["text"])
            accepted, labels = rule is not None, rule.selected_agents if rule else []
            stage, reason = (
                ("rules", None)
                if rule
                else (
                    "not_evaluated",
                    "conditional" if conditional else "needs_classifier",
                )
            )
        rows.append(
            {
                **case,
                "accepted": accepted,
                "predicted": labels,
                "stage": stage,
                "reason": reason,
                "exactMatch": set(labels) == set(case["labels"]) if accepted else None,
                "unsafeAcceptance": accepted and case["mustEscalate"],
                "milliseconds": round((time.perf_counter() - start) * 1000, 3),
            }
        )
    accepted = [r for r in rows if r["accepted"]]
    stages = {
        stage: sum(r["stage"] == stage for r in rows)
        for stage in sorted({r["stage"] for r in rows})
    }
    tp = sum(len(set(r["predicted"]) & set(r["labels"])) for r in accepted)
    fp = sum(len(set(r["predicted"]) - set(r["labels"])) for r in accepted)
    fn = sum(len(set(r["labels"]) - set(r["predicted"])) for r in accepted)
    settings = get_settings()
    return {
        "mode": "live_local_cascade" if live else "rules_only_no_classifier",
        "count": len(rows),
        "backend": settings.intent_backend if live else None,
        "classifierModel": settings.intent_jev_model
        if live and settings.intent_backend == "jev"
        else None,
        "acceptanceThreshold": settings.intent_jev_acceptance_threshold
        if live and settings.intent_backend == "jev"
        else None,
        "acceptedCount": len(accepted),
        "acceptedExactMatchCount": sum(r["exactMatch"] for r in accepted),
        "unsafeAcceptanceCount": sum(r["unsafeAcceptance"] for r in rows),
        "acceptedExactMatchRate": sum(r["exactMatch"] for r in accepted) / len(accepted)
        if accepted
        else None,
        "coverage": len(accepted) / len(rows),
        "stages": stages,
        "acceptedMicroF1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
        "cases": rows,
    }


def confirmation_benchmark():
    from app.graphs.hospital.confirmation import decision_from_text

    groups = {
        "approve": ["确认", "同意", "好的", "可以", "就这个", "挂吧", "退吧", "OK"],
        "reject": [
            "取消",
            "不用了",
            "不挂了",
            "算了",
            "不要",
            "先不退",
            "再想想吧",
            "no",
        ],
        "ordinary_message": [
            "确认一下医生是男的吗",
            "可以先告诉我多少钱吗",
            "好的但我要换医生",
            "如果没有副作用就同意",
            "先别挂我问一下",
            "我想取消之前的那个",
            "同意之后能退款吗",
            "不要取消我的预约",
            "挂吧不过时间换成明天",
            "确认取消还是确认挂号",
            "帮我确认有多少余号",
            "确定是李医生吗",
            "好的这个费用包括检查吗",
            "取消会扣钱吗",
            "我还没想好",
            "",
        ],
    }
    rows = []
    for group, texts in groups.items():
        expected = None if group == "ordinary_message" else group
        for text in texts:
            predicted = decision_from_text(text)
            rows.append(
                {
                    "text": text,
                    "expected": expected,
                    "predicted": predicted,
                    "passed": predicted == expected,
                }
            )
    return {
        "cases": rows,
        "count": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "ordinaryMessageCount": len(groups["ordinary_message"]),
        "ordinaryMessageMisinterpreted": sum(
            r["expected"] is None and r["predicted"] is not None for r in rows
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live-intent",
        action="store_true",
        help="Calls configured classifier for non-rule cases; may incur provider charges",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from loguru import logger

    logger.remove()  # Report inputs are synthetic; provider diagnostics need not be persisted.
    if not args.live_intent:
        for key, value in {
            "DASHSCOPE_CHAT_MODEL": "test-model",
            "DASHSCOPE_API_KEY": "test-key",
            "DASHSCOPE_BASE_URL": "https://example.invalid/v1",
        }.items():
            os.environ.setdefault(key, value)
    report = {
        "evaluatedAt": datetime.now(UTC).isoformat(),
        "syntheticDataOnly": True,
        "datasetNotIndependentHoldout": True,
        "context": context_benchmark(),
        "intent": intent_benchmark(args.live_intent),
        "confirmationText": confirmation_benchmark(),
    }
    files = [
        "scripts/quantify_highlights.py",
        "tests/fixtures/highlight_intent_cases.jsonl",
        "app/graphs/hospital/context_builder.py",
        "app/graphs/hospital/tokens.py",
        "app/intent/cascade.py",
        "app/intent/rules.py",
        "app/intent/jev_classifier.py",
    ]
    report["sourceSha256"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "contextCases": len(report["context"]["cases"]),
                "intent": {k: v for k, v in report["intent"].items() if k != "cases"},
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
