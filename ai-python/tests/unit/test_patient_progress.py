import asyncio
import json

import pytest
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphInterrupt

from app.api.routes.chat import _chat_events
from app.graphs.hospital.nodes import final as final_module
from app.graphs.hospital.reply_sections import compose_reply_sections
from app.graphs.hospital.tools.context import HospitalToolContext
from app.observability import progress


def planned_state():
    return {
        "selected_agents": ["knowledge", "tools"],
        "task_plan": {"tasks": [
            {"agent": "knowledge", "goal": "介绍注意事项", "depends_on": []},
            {"agent": "tools", "goal": "查对应科室号源", "depends_on": ["knowledge"]},
        ]},
    }


def test_sections_preserve_sources_and_avoid_a_second_model_call(monkeypatch):
    state = {**planned_state(), "knowledge_reply": "如加重请就医。\n[来源](https://example.com)", "tools_reply": "内科（排班id=123），余号 2，费用 50 元。"}
    monkeypatch.setattr(final_module, "_summarize_replies", lambda _: pytest.fail("unnecessary rewrite"))
    reply = final_module.final_node(state)["final_reply"]
    assert reply == compose_reply_sections(state)
    assert "https://example.com" in reply
    assert "如加重请就医" in reply
    assert "余号 2，费用 50 元" in reply
    assert "id=" not in reply


def test_planner_fallback_retains_existing_summarizer(monkeypatch):
    state = {"selected_agents": ["knowledge", "tools"], "knowledge_reply": "a", "tools_reply": "b"}
    monkeypatch.setattr(final_module, "_summarize_replies", lambda _: "整理后的回复")
    assert final_module.final_node(state)["final_reply"] == "整理后的回复"


def test_progress_distinguishes_pause_from_failure_and_never_exposes_exceptions(monkeypatch):
    events = []
    monkeypatch.setattr(progress, "get_stream_writer", lambda: events.append)
    with pytest.raises(GraphInterrupt):
        with progress.progress_step("business"):
            raise GraphInterrupt(())
    assert [event["step"]["status"] for event in events] == ["running", "waiting"]
    events.clear()
    with pytest.raises(ValueError):
        with progress.progress_step("web"):
            raise ValueError("SECRET tool args")
    assert events[-1]["step"]["status"] == "failed"
    assert "SECRET" not in json.dumps(events)


def test_custom_event_boundary_rebuilds_whitelisted_labels():
    assert progress.public_progress({"type": "other", "content": "SECRET"}) is None
    event = progress.public_progress({"type": "progress", "step": {
        "id": "web:1", "key": "web", "status": "running", "label": "SECRET", "args": "SECRET",
    }})
    assert event["content"] == "检索公开医疗资料"
    assert "SECRET" not in json.dumps(event)


def test_completed_knowledge_arrives_before_business_without_stale_or_duplicate_text():
    state = planned_state()
    knowledge = "请按需就医。\n[来源](https://example.com)"
    business = "明天上午内科余号 2。"

    class Graph:
        async def astream(self, *args, **kwargs):
            yield {"type": "values", "data": {**state, "knowledge_reply": "上轮医疗内容", "tools_reply": "上轮号源"}}
            yield {"type": "updates", "data": {"begin_node": {"selected_agents": state["selected_agents"], "task_plan": None, "knowledge_reply": None, "tools_reply": None}}}
            yield {"type": "updates", "data": {"plan_node": {"task_plan": state["task_plan"]}}}
            yield {"type": "custom", "data": {"type": "private", "content": "SECRET"}}
            yield {"type": "updates", "ns": ("knowledge_node:x",), "data": {"model": {"knowledge_reply": "内部草稿"}}}
            yield {"type": "updates", "data": {"knowledge_node": {"knowledge_reply": knowledge, "rag_sources": [{"id": "S1", "title": "资料"}]}}}
            yield {"type": "custom", "data": {"type": "progress", "step": {"id": "business:x", "key": "business", "status": "running"}}}
            yield {"type": "updates", "data": {"tool_node": {"tools_reply": business}}}
            completed = {**state, "knowledge_reply": knowledge, "tools_reply": business}
            completed["final_reply"] = compose_reply_sections(completed)
            yield {"type": "updates", "data": {"final_node": {"final_reply": completed["final_reply"]}}}
            yield {"type": "values", "data": completed}

    async def collect():
        stream = _chat_events(
            graph_instance=Graph(), graph_input={"messages": [HumanMessage(content="test")]},
            context=HospitalToolContext(""), config={}, conversation_id="test",
            fast_mode=False, request_id="test", thread_id="test", checkpoint_hit=False, rehydrated=False,
        )
        return [json.loads(item.removeprefix("data: ").strip()) async for item in stream]

    events = asyncio.run(collect())
    tokens = [event["content"] for event in events if event["type"] == "token"]
    first = next(i for i, event in enumerate(events) if event["type"] == "token")
    querying = next(i for i, event in enumerate(events) if event.get("step", {}).get("id") == "business:x")
    assert first < querying
    assert len(tokens) == 2
    assert "".join(tokens) == events[-1]["reply"]
    assert len([event for event in events if event["type"] == "citation"]) == 1
    assert all(word not in json.dumps(events, ensure_ascii=False) for word in ("上轮", "内部草稿", "SECRET"))
