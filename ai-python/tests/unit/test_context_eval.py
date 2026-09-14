import json
from pathlib import Path

from scripts.evaluate_context import evaluate


def test_context_eval_dataset_has_sixty_cases_and_no_core_failures():
    dataset = Path(__file__).resolve().parents[2] / "evals" / "context_cases.jsonl"
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]

    report, failures = evaluate(cases)

    assert len(cases) >= 60
    assert failures == []
    assert report["executed_against_code"] is True
    assert report["context_recall"] == 1.0
    assert report["cross_user_leak_rate"] == 0.0
    assert report["error_memory_rate"] == 0.0


def test_context_eval_blocks_cross_user_leakage():
    _, failures = evaluate([{
        "id": "leak",
        "owner": "user-a",
        "selected_owner": "user-b",
    }])

    assert failures == ["leak: cross-user context leak"]
