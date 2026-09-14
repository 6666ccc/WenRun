import pytest

from app.intent.metrics import record_route, reset_route_metrics, route_metrics_snapshot


@pytest.fixture(autouse=True)
def clean_metrics():
    reset_route_metrics()
    yield
    reset_route_metrics()


def test_route_metrics_aggregate_only_low_cardinality_dimensions():
    record_route(
        {
            "stage": "rules",
            "safety_flags": ["breathing_difficulty"],
        },
        fallback=False,
        out_of_scope=False,
    )
    record_route(
        {
            "stage": "llm",
            "escalation_reason": "low_confidence",
            "safety_flags": [],
        },
        fallback=False,
        out_of_scope=True,
    )
    record_route(
        {
            "stage": "fallback",
            "escalation_reason": "lightweight_model_unavailable",
            "safety_flags": [],
        },
        fallback=True,
        out_of_scope=False,
    )

    snapshot = route_metrics_snapshot()

    assert snapshot == {
        "total": 3,
        "localCoverage": 0.3333,
        "stageCounts": {"rules": 1, "llm": 1, "fallback": 1},
        "escalationReasons": {
            "low_confidence": 1,
            "lightweight_model_unavailable": 1,
        },
        "safetyFlagCounts": {"breathing_difficulty": 1},
        "fallbackCount": 1,
        "outOfScopeCount": 1,
        "scope": "current_process",
    }
