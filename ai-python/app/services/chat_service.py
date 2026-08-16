from collections.abc import AsyncIterator

from langgraph.types import Command

from app.api.dependencies.runtime import ToolRuntimeContext
from app.core.logging import log_event
from app.graphs.hospital.graph import graph_config
from app.models.chat import ChatRequest, ChatResponse, ResumeRequest
from app.models.source import CitationSource, ToolSource
from app.models.sse import ChatStreamEvent

NODE_STATUS = {
    "load_memory": "加载记忆",
    "intent_judgment": "识别意图",
    "chat": "整理回复",
    "hospital": "查询医院信息",
    "medical": "检索医疗资料",
    "clarify": "确认意图",
    "registration_interrupt": "等待确认",
    "citation_validate": "校验引用",
    "save_memory": "保存记忆",
}

_INTERRUPT_ERRORS = {"GraphInterrupt", "NodeInterrupt"}
_service = None


class ChatServiceError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ChatService:
    def __init__(self, checkpointer=None, vector_memory=None, graph=None):
        self._checkpointer = checkpointer
        self._vector_memory = vector_memory
        self._graph = graph
        self._interrupt_owners: dict[str, str] = {}
        self._resolved_interrupts: set[str] = set()

    async def invoke_chat(
        self,
        request: ChatRequest,
        runtime: ToolRuntimeContext,
    ) -> ChatResponse:
        if self._graph is None:
            return ChatResponse(
                reply=None,
                status="completed",
                conversation_id=request.conversation_id,
            )
        result = await self._graph.ainvoke(
            _initial_state(request),
            graph_config(request.conversation_id, runtime.delegation_token),
        )
        interrupt = self._remember_interrupt(request.conversation_id, result)
        return ChatResponse(
            reply=_last_text(result),
            status="pending" if interrupt else "completed",
            conversation_id=request.conversation_id,
            intent=result.get("intent") if isinstance(result, dict) else None,
            interrupts=[interrupt] if interrupt else [],
        )

    async def stream_chat(
        self,
        request: ChatRequest,
        runtime: ToolRuntimeContext,
    ) -> AsyncIterator[ChatStreamEvent]:
        if self._graph is None:
            yield ChatStreamEvent(
                type="done",
                conversation_id=request.conversation_id,
                status="completed",
            )
            return
        log_event(conversation_id=request.conversation_id, node="stream_chat")
        config = graph_config(request.conversation_id, runtime.delegation_token)
        async for event in self._stream_graph(_initial_state(request), config, request.conversation_id):
            yield event

    async def resume_stream(
        self,
        request: ResumeRequest,
        runtime: ToolRuntimeContext,
    ) -> AsyncIterator[ChatStreamEvent]:
        if self._graph is None:
            yield ChatStreamEvent(
                type="done",
                conversation_id=request.conversation_id,
                status="completed",
            )
            return
        config = graph_config(request.conversation_id, runtime.delegation_token)
        self._guard_resume(request, config)
        command = Command(
            resume={
                "interruptId": request.interrupt_id,
                "approved": request.approved,
                "params": request.params,
            }
        )
        async for event in self._stream_graph(command, config, request.conversation_id):
            yield event
        self._resolved_interrupts.add(request.interrupt_id)
        self._interrupt_owners.pop(request.interrupt_id, None)

    async def delete_conversation(self, conversation_id: str) -> None:
        if self._checkpointer is not None:
            self._checkpointer.delete_thread(conversation_id)
        if self._vector_memory is not None:
            await self._vector_memory.delete_memory(conversation_id)
        stale = [key for key, owner in self._interrupt_owners.items() if owner == conversation_id]
        for key in stale:
            self._interrupt_owners.pop(key, None)
            self._resolved_interrupts.discard(key)

    async def _stream_graph(self, payload, config, conversation_id: str) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="status", content="routing", conversation_id=conversation_id)
        merged: dict = {}
        try:
            async for chunk in self._graph.astream(payload, config, stream_mode="updates"):
                if not isinstance(chunk, dict):
                    continue
                for node, update in chunk.items():
                    status = NODE_STATUS.get(node)
                    if status:
                        yield ChatStreamEvent(
                            type="status",
                            content=status,
                            conversation_id=conversation_id,
                        )
                    if isinstance(update, dict):
                        merged.update(update)
                        error = update.get("error")
                        if error:
                            yield ChatStreamEvent(
                                type="error",
                                code=error.get("code"),
                                message=error.get("message"),
                                conversation_id=conversation_id,
                            )
                            return
        except Exception as exc:
            if exc.__class__.__name__ not in _INTERRUPT_ERRORS:
                raise
        result = _final_result(self._graph, config, merged)
        interrupt = self._remember_interrupt(conversation_id, result)
        if interrupt and not result.get("__interrupt__"):
            result = {**result, "__interrupt__": [_Interrupt(interrupt)]}
        async for event in _events_from_result(result, conversation_id):
            yield event

    def _remember_interrupt(self, conversation_id: str, result) -> dict | None:
        interrupt = _interrupt_payload(result) or _active_interrupt(self._graph, graph_config(conversation_id, None))
        interrupt_id = interrupt.get("interruptId") if interrupt else None
        if interrupt_id:
            self._interrupt_owners[interrupt_id] = conversation_id
        return interrupt

    def _guard_resume(self, request: ResumeRequest, config) -> None:
        owner = self._interrupt_owners.get(request.interrupt_id)
        if owner and owner != request.conversation_id:
            raise ChatServiceError("INTERRUPT_CONVERSATION_MISMATCH", "确认请求与当前会话不匹配")
        pending = _active_interrupt(self._graph, config)
        if pending is None:
            if request.interrupt_id in self._resolved_interrupts:
                raise ChatServiceError("INTERRUPT_ALREADY_RESOLVED", "该确认请求已经处理")
            raise ChatServiceError("INTERRUPT_EXPIRED", "确认请求已过期，请重新发起")
        pending_id = pending.get("interruptId")
        if pending_id and pending_id != request.interrupt_id:
            raise ChatServiceError("INTERRUPT_CONVERSATION_MISMATCH", "确认请求与当前会话不匹配")


class _Interrupt:
    def __init__(self, value):
        self.value = value


def create_chat_service(*, settings=None, deps=None, checkpointer=None, vector_memory=None) -> ChatService:
    from app.core.config import get_settings
    from app.graphs.hospital.checkpoint import get_checkpointer
    from app.graphs.hospital.graph import build_graph
    from app.graphs.hospital.runtime import build_production_dependencies
    from app.services.memory.vector import VectorMemory

    settings = settings or get_settings()
    checkpointer = checkpointer or get_checkpointer(settings)
    if vector_memory is None:
        vector_memory = VectorMemory(store_factory=_memory_store_factory(settings))
    if deps is None:
        deps = build_production_dependencies(settings, vector_memory=vector_memory)
    graph = build_graph(deps, checkpointer=checkpointer)
    return ChatService(checkpointer=checkpointer, vector_memory=vector_memory, graph=graph)


def get_chat_service() -> ChatService:
    global _service
    if _service is None:
        _service = create_chat_service()
    return _service


def reset_chat_service() -> None:
    global _service
    _service = None


def _memory_store_factory(settings):
    def factory():
        from app.core.llm import create_embeddings
        from app.rag.collections import KnowledgeBase
        from app.rag.qdrant import get_vector_store

        return get_vector_store(settings, KnowledgeBase.MEMORY, create_embeddings(settings))

    return factory


def _initial_state(request: ChatRequest) -> dict:
    context = request.user_context
    return {
        "messages": [{"role": "user", "content": request.message}],
        "conversation_id": request.conversation_id,
        "user_id": context.user_id,
        "patient_id": context.patient_id,
        "intent": None,
        "memory_enabled": request.memory_enabled,
        "task_plan": [],
        "tool_context": {},
        "sources": [],
        "pending_action": None,
        "error": None,
        "retry_count": 0,
    }


async def _events_from_result(result: dict, conversation_id: str) -> AsyncIterator[ChatStreamEvent]:
    error = result.get("error") if isinstance(result, dict) else None
    if error:
        yield ChatStreamEvent(
            type="error",
            code=error.get("code"),
            message=error.get("message"),
            conversation_id=conversation_id,
        )
        return
    interrupt = _interrupt_payload(result)
    if interrupt:
        yield ChatStreamEvent(
            type="interrupt",
            interrupt=interrupt,
            conversation_id=conversation_id,
            status="pending",
        )
        return
    sources = _event_sources(result.get("sources") if isinstance(result, dict) else None)
    text = _last_text(result) or ""
    if sources:
        yield ChatStreamEvent(
            type="citation",
            sources=sources,
            conversation_id=conversation_id,
        )
    if text:
        yield ChatStreamEvent(
            type="token",
            content=text,
            conversation_id=conversation_id,
        )
    yield ChatStreamEvent(
        type="done",
        conversation_id=conversation_id,
        status="completed",
        intent=result.get("intent") if isinstance(result, dict) else None,
        content=text,
        reply=text,
        sources=sources,
    )


def _event_sources(raw) -> list | None:
    if not raw:
        return None
    sources = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            if item.get("toolName") or item.get("kind") == "tool":
                sources.append(ToolSource.model_validate(item))
            else:
                sources.append(CitationSource.model_validate(item))
        except Exception:
            continue
    return sources or None


def _final_result(graph, config, merged: dict) -> dict:
    try:
        snapshot = graph.get_state(config)
        values = dict(snapshot.values or {})
        interrupt = _active_interrupt(graph, config)
        if interrupt:
            values["__interrupt__"] = [_Interrupt(interrupt)]
        if values:
            return values
    except Exception:
        pass
    return merged


def _interrupt_payload(result) -> dict | None:
    interrupts = None
    if isinstance(result, dict):
        interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    value = getattr(first, "value", first)
    return value if isinstance(value, dict) else {"value": value}


def _active_interrupt(graph, config) -> dict | None:
    if graph is None:
        return None
    try:
        snapshot = graph.get_state(config)
    except Exception:
        return None
    interrupts = getattr(snapshot, "interrupts", None) or ()
    if interrupts:
        value = getattr(interrupts[0], "value", interrupts[0])
        return value if isinstance(value, dict) else None
    for task in getattr(snapshot, "tasks", ()) or ():
        task_interrupts = getattr(task, "interrupts", None) or ()
        if task_interrupts:
            value = getattr(task_interrupts[0], "value", task_interrupts[0])
            return value if isinstance(value, dict) else None
    return None


def _last_text(result) -> str | None:
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return None
    last = messages[-1]
    if isinstance(last, dict):
        return last.get("content")
    return getattr(last, "content", None)
