import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from app.graphs.hospital.tokens import estimate_tokens
from app.models.budgeted import BudgetedChatModel


class Provider(BaseChatModel):
    calls: list = Field(default_factory=list)
    failures: int = 0
    partial: bool = False

    @property
    def _llm_type(self):
        return "fake"

    def _generate(self, messages, **kwargs):
        self.calls.append(messages)
        if len(self.calls) <= self.failures:
            raise RuntimeError("context_length_exceeded")
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="完成"))]
        )

    def _stream(self, messages, **kwargs):
        self.calls.append(messages)
        if self.partial:
            yield ChatGenerationChunk(message=AIMessageChunk(content="已输出"))
        if len(self.calls) <= self.failures:
            raise RuntimeError("context_length_exceeded")
        yield ChatGenerationChunk(message=AIMessageChunk(content="完成"))


def messages():
    return [
        SystemMessage(content="系统规则"),
        *[HumanMessage(content="历史" * 600) for _ in range(8)],
        HumanMessage(content="当前问题必须完整保留"),
    ]


def test_retry_only_failed_invocation_with_smaller_complete_history():
    delegate = Provider(failures=2)
    answer = BudgetedChatModel(delegate=delegate).invoke(messages())
    assert answer.content == "完成"
    assert len(delegate.calls) == 3
    assert all(
        call[0].content == "系统规则" and call[-1].content == "当前问题必须完整保留"
        for call in delegate.calls
    )
    assert estimate_tokens(delegate.calls[2]) < estimate_tokens(delegate.calls[0])


def test_overflow_exhausts_after_two_retries():
    delegate = Provider(failures=10)
    with pytest.raises(RuntimeError):
        BudgetedChatModel(delegate=delegate).invoke(messages())
    assert len(delegate.calls) == 3


def test_stream_never_retries_after_visible_output():
    delegate = Provider(failures=2, partial=True)
    with pytest.raises(RuntimeError):
        list(BudgetedChatModel(delegate=delegate).stream(messages()))
    assert len(delegate.calls) == 1


def test_tool_schema_and_pairs_are_in_final_budget():
    from langchain_core.messages import ToolMessage

    from app.graphs.hospital.context_builder import assemble_messages

    tool_schema = [
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": "资料" * 200,
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    call = AIMessage(content="", tool_calls=[{"name": "read", "args": {}, "id": "t"}])
    result = ToolMessage(content="完整结果", tool_call_id="t")
    output = assemble_messages(
        [*messages(), call, result], tools=tool_schema, purpose="tools"
    )
    assert call in output and result in output
    assert estimate_tokens(output, tools=tool_schema) <= 8000


def test_agent_retry_does_not_replay_successful_write_tool():
    from langchain.agents import create_agent
    from langchain.tools import tool

    writes = []

    @tool
    def save_once() -> str:
        """Test-only write operation."""
        writes.append(True)
        return "已保存"

    class LoopProvider(Provider):
        def _generate(self, messages, **kwargs):
            self.calls.append(messages)
            if len(self.calls) == 1:
                answer = AIMessage(
                    content="",
                    tool_calls=[{"id": "write", "name": "save_once", "args": {}}],
                )
            elif len(self.calls) == 2:
                raise RuntimeError("context_length_exceeded")
            else:
                answer = AIMessage(content="完成")
            return ChatResult(generations=[ChatGeneration(message=answer)])

    delegate = LoopProvider()
    agent = create_agent(
        BudgetedChatModel(delegate=delegate, purpose="tools"), [save_once]
    )
    result = agent.invoke({"messages": [HumanMessage(content="请保存测试记录")]})
    assert result["messages"][-1].content == "完成"
    assert len(delegate.calls) == 3
    assert writes == [True]
