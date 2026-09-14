from loguru import logger

from app.observability.context_metrics import (
    begin_context_trace,
    current_context_trace,
    record_context,
    record_retrieval,
    record_summary,
    record_tool_names,
)


def test_context_trace_records_counts_without_raw_thread_or_patient_text():
    captured = []
    sink = logger.add(captured.append, format="{message}")
    try:
        trace = begin_context_trace(
            request_id="request-1",
            thread_id="user:7:conversation:patient-secret",
            mode="normal",
            checkpoint_hit=True,
            rehydrated=False,
        )
        record_context(
            purpose="chat",
            data_tokens=20,
            recent_tokens=40,
            memory_count=2,
            summary_version=3,
        )
        record_retrieval(count=2, tokens=100, rejected=1)
        record_tool_names({"list_schedules"})
        record_summary(4)
        trace.first_token_ms = 25
        trace.finish()
    finally:
        logger.remove(sink)

    output = "".join(str(item) for item in captured)
    assert "patient-secret" not in output
    assert "list_schedules" in output
    assert '"memory_count": 2' in output
    assert '"rag_count": 2' in output
    assert current_context_trace() is None
