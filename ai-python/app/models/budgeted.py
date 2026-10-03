"""Budget and retry one provider call, including calls inside an Agent.

Delegating at BaseChatModel's generation boundary never replays tools or a graph.
The public BaseChatModel owns callbacks; the delegate does not emit a second set.
"""

from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool


def is_context_overflow(error: Exception) -> bool:
    body = getattr(error, "body", None)
    code = getattr(error, "code", None)
    # Error text is inspected locally, never logged with patient input.
    value = f"{type(error).__name__} {code} {body} {error}".lower()
    return any(
        marker in value
        for marker in (
            "context_length_exceeded",
            "openaicontextoverflowerror",
            "input tokens exceed",
            "prompt is too long",
            "maximum context length",
        )
    )


class BudgetedChatModel(BaseChatModel):
    delegate: BaseChatModel
    purpose: str = "chat"

    @property
    def _llm_type(self) -> str:
        return "hospital-budgeted-chat"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": getattr(self.delegate, "model_name", "configured-model")}

    def bind_tools(self, tools: Sequence, *, tool_choice=None, **kwargs):
        options = {"tools": [convert_to_openai_tool(tool) for tool in tools], **kwargs}
        if tool_choice is not None:
            options["tool_choice"] = tool_choice
        return self.bind(**options)

    def _prepare(self, messages, kwargs, attempt, run_manager):
        from app.graphs.hospital.context_builder import assemble_messages

        return assemble_messages(
            messages,
            tools=kwargs.get("tools"),
            purpose=self.purpose,
            budget_scale=0.65**attempt,
        )

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        from app.observability.context_metrics import record_event

        for attempt in range(3):
            prepared = self._prepare(messages, kwargs, attempt, run_manager)
            try:
                return self.delegate._generate(prepared, stop=stop, **kwargs)
            except Exception as error:
                if not is_context_overflow(error):
                    raise
                record_event("contextOverflowCount")
                if attempt == 2:
                    record_event("contextRetryFailures")
                    raise
                record_event("contextRetryCount")
        raise AssertionError("unreachable")

    def _stream(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> Iterator[ChatGenerationChunk]:
        from app.observability.context_metrics import record_event

        for attempt in range(3):
            prepared = self._prepare(messages, kwargs, attempt, run_manager)
            emitted = False
            try:
                for chunk in self.delegate._stream(prepared, stop=stop, **kwargs):
                    # Even a tool-call fragment must not be duplicated on retry.
                    emitted = emitted or bool(
                        chunk.message.content
                        or getattr(chunk.message, "tool_call_chunks", None)
                    )
                    yield chunk
                return
            except Exception as error:
                if not is_context_overflow(error):
                    raise
                record_event("contextOverflowCount")
                if emitted or attempt == 2:
                    record_event("contextRetryFailures")
                    raise
                record_event("contextRetryCount")
