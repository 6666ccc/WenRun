import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from datetime import datetime

from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from app.graphs.hospital.nodes import chat as chat_mod
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext

FROZEN_NOW = datetime(2026, 9, 1, 11, 15, tzinfo=CLINIC_TZ)
CONTEXT = HospitalToolContext("delegated-token", "trace-123", now=FROZEN_NOW)


def _graph_runtime(context: HospitalToolContext) -> Runtime:
    return Runtime(context=context)


def test_chat_system_prompt_includes_beijing_clock():
    prompt = chat_mod.build_chat_system_prompt(FROZEN_NOW)

    assert "当前时间：2026-09-01 星期二 11:15（北京时间）。" in prompt
    assert prompt.startswith(chat_mod.CHAT_SYSTEM_PROMPT)


def test_chat_prompt_answers_weekday_from_clock():
    assert "星期几" in chat_mod.CHAT_SYSTEM_PROMPT


def test_chat_node_streams_with_request_clock(monkeypatch):
    captured: dict = {}

    class FakeModel:
        def stream(self, messages):
            captured["messages"] = messages
            yield type("Chunk", (), {"content": "今天是星期二。"})()

    monkeypatch.setattr(chat_mod, "model", FakeModel())
    result = chat_mod.chat_node(
        {
            "selected_agents": ["chat"],
            "messages": [HumanMessage(content="今天星期几")],
        },
        _graph_runtime(CONTEXT),
    )

    assert result == {"chat_reply": "今天是星期二。"}
    system = captured["messages"][0]
    assert "当前时间：2026-09-01 星期二 11:15（北京时间）。" in system.content
