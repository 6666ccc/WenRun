"""Separate deterministic faults from live-model quality probes (synthetic data only)."""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def deterministic_cases():
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.graphs.hospital.context_builder import (
        ContextBudgetError,
        assemble_messages,
        build_context,
        coerce_summary,
    )
    from app.graphs.hospital.nodes.knowledge import necessary_clinical_scopes
    from app.graphs.hospital.state import ConversationSummary
    from app.graphs.hospital.tokens import estimate_tokens
    from app.graphs.hospital.tools.medical_source import is_authoritative_url

    results = []
    for line in (
        (ROOT / "tests/fixtures/context_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        case = json.loads(line)
        try:
            kind = case["kind"]
            if kind == "projection":
                result = build_context(
                    {
                        "messages": [HumanMessage(content="继续")],
                        "summary": {
                            "patient_self_reports": ["咳嗽自述"],
                            "pending_tasks": ["选择科室"],
                        },
                    },
                    purpose=case["purpose"],
                )
                assert ("咳嗽自述" in str(result)) == case["clinical"]
            elif kind == "schema":
                try:
                    ConversationSummary.model_validate(
                        {"schema_version": 2, case["field"]: []}
                    )
                except ValueError:
                    pass
                else:
                    raise AssertionError("removed field accepted")
            elif kind == "migration":
                migrated = coerce_summary(
                    {
                        "preferences": ["旧偏好"],
                        "verified_business_facts": ["旧事实"],
                        "pending_tasks": [case["pending"]],
                        "version": 2,
                    }
                )
                assert migrated.pending_tasks == [case["pending"]]
                assert "verified_business_facts" not in migrated.model_dump()
            elif kind == "budget":
                latest = HumanMessage(content="本轮完整问题")
                messages = [
                    SystemMessage(content="完整规则"),
                    *[
                        HumanMessage(content="历史" * 500)
                        for _ in range(case["history"])
                    ],
                    latest,
                ]
                result = assemble_messages(messages, purpose=case["purpose"])
                assert result[-1] is latest and estimate_tokens(result) <= 8000
            elif kind == "oversize":
                try:
                    assemble_messages(
                        [HumanMessage(content="长问题" * case["repeat"])],
                        purpose="chat",
                    )
                except ContextBudgetError as error:
                    assert "缩短" in str(error) or "分段" in str(error)
                else:
                    raise AssertionError("oversized patient message was accepted")
            elif kind == "authority":
                assert is_authoritative_url(case["url"]) == case["allowed"]
            elif kind == "scopes":
                assert necessary_clinical_scopes(case["query"]) == case["expected"]
            else:
                raise ValueError("unknown fixture kind")
            results.append({"id": case["id"], "passed": True})
        except Exception as error:  # noqa: BLE001 - record individual case failures without input text
            results.append(
                {"id": case["id"], "passed": False, "errorType": type(error).__name__}
            )
    return results


def real_model_cases():
    import re

    from langchain_core.messages import HumanMessage, SystemMessage

    from app.graphs.hospital.nodes.knowledge import PERSONALIZATION_RULES
    from app.graphs.hospital.nodes.summarize import _build_prompt, _parse_summary
    from app.models.chat import model

    results = []
    for line in (
        (ROOT / "tests/fixtures/context_quality_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ):
        case = json.loads(line)
        try:
            if case["kind"] == "summary":
                response = model.model_copy(update={"purpose": "summary"}).invoke(
                    _build_prompt(case.get("existing"), case["transcript"])
                )
                parsed = _parse_summary(response.content)
                assert parsed is not None
                text = " ".join(parsed.pending_tasks)
                results.append(
                    {
                        "id": case["id"],
                        "validSchema": True,
                        "keywordRecall": sum(word in text for word in case["keywords"])
                        / max(1, len(case["keywords"])),
                        "candidate": parsed.model_dump(),
                    }
                )
            else:
                response = model.model_copy(update={"purpose": "knowledge"}).invoke(
                    [
                        SystemMessage(content=PERSONALIZATION_RULES),
                        HumanMessage(content=case["question"]),
                    ]
                )
                results.append(
                    {
                        "id": case["id"],
                        "individualDoseAbsent": not bool(
                            re.search(
                                r"\d+(?:\.\d+)?\s*(mg|毫克|ml|毫升)",
                                response.content,
                                re.IGNORECASE,
                            )
                        ),
                        "response": response.content,
                    }
                )
        except Exception as error:  # noqa: BLE001 - record provider category without provider body
            results.append({"id": case["id"], "errorType": type(error).__name__})
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--real-model",
        action="store_true",
        help="Use configured live provider; synthetic quality samples only",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "context-evaluation.json")
    args = parser.parse_args()
    if not args.real_model:
        for key, value in {
            "DASHSCOPE_CHAT_MODEL": "test-model",
            "DASHSCOPE_API_KEY": "test-key",
            "DASHSCOPE_BASE_URL": "https://example.invalid/v1",
        }.items():
            os.environ.setdefault(key, value)
    results = real_model_cases() if args.real_model else deterministic_cases()
    fault_exit = None
    if not args.real_model:
        fault_exit = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/unit/test_summary_commit.py",
                "tests/unit/test_budgeted_model.py",
                "tests/unit/test_full_recovery.py",
                "tests/unit/test_confirmation_kinds.py",
                "tests/unit/test_turn_isolation.py",
                "tests/unit/test_graph_topology.py",
            ],
            cwd=ROOT,
            check=False,
        ).returncode
    report = {
        "evaluatedAt": datetime.now(UTC).isoformat(),
        "kind": "real_model_quality"
        if args.real_model
        else "deterministic_engineering",
        "syntheticDataOnly": True,
        "semanticReviewRequired": args.real_model,
        "faultTestsExitCode": fault_exit,
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "kind": report["kind"],
                "cases": len(results),
                "errors": sum(
                    "errorType" in item or item.get("passed") is False
                    for item in results
                ),
                "faultTestsExitCode": fault_exit,
            },
            ensure_ascii=False,
        )
    )
    return int(
        fault_exit not in (None, 0)
        or any("errorType" in item or item.get("passed") is False for item in results)
    )


if __name__ == "__main__":
    raise SystemExit(main())
