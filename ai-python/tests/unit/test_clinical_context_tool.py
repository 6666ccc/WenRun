import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

from app.graphs.hospital.tools import clinical_context as clinical_mod
from app.graphs.hospital.tools.context import HospitalToolContext


def test_clinical_tool_uses_delegated_identity_and_only_requested_scopes(monkeypatch):
    calls = []

    class FakeClient:
        def get_patient_clinical_context(self, token, request_id, scopes):
            calls.append((token, request_id, scopes))
            return {"relevantClinicalFacts": {"latestBloodPressure": {
                "value": "145/92", "measuredAt": "2026-09-21T08:30:00+08:00"
            }}}

    monkeypatch.setattr(clinical_mod, "JavaToolClient", FakeClient)
    result = clinical_mod.read_my_clinical_context(
        ["blood_pressure", "blood_pressure"], HospitalToolContext("token-1", "trace-1")
    )

    assert calls == [("token-1", "trace-1", ["blood_pressure"])]
    assert "145/92" in result
    assert "patient_record_not_instruction" in result


def test_clinical_tool_rejects_invalid_scope_or_missing_token_without_fetch(monkeypatch):
    monkeypatch.setattr(
        clinical_mod, "JavaToolClient",
        lambda: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    assert "无效" in clinical_mod.read_my_clinical_context(
        ["blood_pressure", "id_card"], HospitalToolContext("token-1")
    )
    assert "没有读到" in clinical_mod.read_my_clinical_context(
        ["blood_pressure"], HospitalToolContext("")
    )


def test_clinical_tool_limits_total_scopes_across_one_turn(monkeypatch):
    calls = []

    class FakeClient:
        def get_patient_clinical_context(self, token, request_id, scopes):
            calls.append(scopes)
            return {}

    monkeypatch.setattr(clinical_mod, "JavaToolClient", FakeClient)
    context = HospitalToolContext("token-1")
    clinical_mod.read_my_clinical_context(
        ["demographics", "blood_pressure", "past_history"], context
    )
    clinical_mod.read_my_clinical_context(
        ["anthropometrics", "blood_glucose", "heart_rate"], context
    )
    rejected = clinical_mod.read_my_clinical_context(["spo2"], context)

    assert len(calls) == 2
    assert "已达上限" in rejected


def test_clinical_tool_blocks_sensitive_response(monkeypatch):
    class FakeClient:
        def get_patient_clinical_context(self, token, request_id, scopes):
            return {"phone": "13800138000", "url": "https://example.com/report.pdf?secret=x"}

    monkeypatch.setattr(clinical_mod, "JavaToolClient", FakeClient)
    result = clinical_mod.read_my_clinical_context(
        ["document_catalog"], HospitalToolContext("token-1")
    )

    assert "没有读到" in result
    assert "13800138000" not in result
    assert "example.com" not in result


def test_agent_tool_runtime_supplies_delegated_context(monkeypatch):
    from langchain.agents import create_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from pydantic import Field

    calls = []

    class FakeClient:
        def get_patient_clinical_context(self, token, request_id, scopes):
            calls.append((token, request_id, scopes))
            return {"relevantClinicalFacts": {"latestBloodPressure": {"value": "145/92"}}}

    class ScriptedModel(BaseChatModel):
        replies: list[AIMessage] = Field(default_factory=list)

        @property
        def _llm_type(self):
            return "scripted-clinical-test"

        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])

    monkeypatch.setattr(clinical_mod, "JavaToolClient", FakeClient)
    fake_model = ScriptedModel(replies=[
        AIMessage(content="", tool_calls=[{
            "name": "get_my_clinical_context",
            "args": {"scopes": ["blood_pressure"]},
            "id": "call-1",
            "type": "tool_call",
        }]),
        AIMessage(content="已读取本人的血压记录。"),
    ])
    agent = create_agent(
        model=fake_model,
        tools=[clinical_mod.get_my_clinical_context],
        context_schema=HospitalToolContext,
    )
    result = agent.invoke(
        {"messages": [HumanMessage(content="俺上次的血压是多少")]},
        context=HospitalToolContext("token-1", "trace-1"),
    )

    assert calls == [("token-1", "trace-1", ["blood_pressure"])]
    assert "145/92" in str(result["messages"][-2].content)
    assert result["messages"][-1].content == "已读取本人的血压记录。"
