import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from loguru import logger
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response, StreamingResponse

from app.api.dependencies.auth import (
    DelegationContext,
    verify_api_key,
    verify_delegation_token,
)
from app.core.logging import current_request_id
from app.graphs.hospital.checkpointing import (
    get_checkpointer,
    get_fast_memory_graph,
    get_memory_graph,
)
from app.graphs.hospital.confirmation import resume_command as _resume_command
from app.graphs.hospital.graphs import fast_graph, graph
from app.graphs.hospital.identity import thread_id_for
from app.graphs.hospital.rehydration import build_rehydrated_messages
from app.graphs.hospital.tools.context import HospitalToolContext
from app.models.chat import ChatRequest, ChatResponse, ChatResumeRequest
from app.observability.context_metrics import begin_context_trace
from app.rag.ingest import (
    deactivate_document,
    delete_document,
    get_document_versions,
    ingest_file,
)

router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)


def _response_from_state(conversation_id: str, result: dict[str, Any]) -> ChatResponse:
    reply = result.get("final_reply")
    if not isinstance(reply, str) or not reply.strip():
        logger.error("chat_graph_missing_final_reply conversation_id={}", conversation_id)
        raise HTTPException(status_code=500, detail="AI 对话未生成有效回复")

    selected_agents: list[str] = []
    for agent_name in result.get("selected_agents") or []:
        if isinstance(agent_name, str):
            selected_agents.append(agent_name)

    sources: list[dict[str, Any]] = []
    for source in result.get("rag_sources") or []:
        if isinstance(source, dict):
            sources.append(source)

    return ChatResponse(
        reply=reply.strip(),
        conversation_id=conversation_id,
        selected_agents=selected_agents,
        sources=sources,
    )


def _assert_request_identity(request: ChatRequest | ChatResumeRequest, delegation: DelegationContext) -> None:
    """浏览器身份字段只能与 JWT 一致，不能覆盖已验证身份。"""

    supplied = request.user_context
    identity = delegation.identity
    if supplied.user_id is not None and supplied.user_id != identity.user_id:
        raise HTTPException(status_code=403, detail="delegated user identity mismatch")
    if supplied.patient_id is not None and supplied.patient_id != identity.patient_id:
        raise HTTPException(status_code=403, detail="delegated patient identity mismatch")


def _initial_state(request: ChatRequest, delegation: DelegationContext) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=request.message)],
        "conversation_id": request.conversation_id,
        "patient_id": delegation.identity.patient_id,
        "long_term_memories": [
            item.model_dump(by_alias=True) for item in request.long_term_memories
        ] if request.memory_enabled else [],
    }


def _runtime_context(
    conversation_id: str,
    delegation: DelegationContext,
    *,
    writes_enabled: bool,
) -> HospitalToolContext:
    """委托令牌与追踪号只在本次请求内有效，绝不进入持久化 State。"""

    return HospitalToolContext(
        delegation.token,
        current_request_id(),
        user_id=delegation.identity.user_id,
        patient_id=delegation.identity.patient_id,
        conversation_id=conversation_id,
        writes_enabled=writes_enabled,
    )


def _graph_for(memory_enabled: bool, fast_mode: bool):
    if memory_enabled:
        memory_graph = get_fast_memory_graph() if fast_mode else get_memory_graph()
        if memory_graph is not None:
            return memory_graph
    return fast_graph if fast_mode else graph


def _graph_config(
    conversation_id: str | ChatRequest,
    delegation: DelegationContext,
) -> dict[str, Any]:
    if isinstance(conversation_id, ChatRequest):
        conversation_id = conversation_id.conversation_id
    return {
        "configurable": {
            "thread_id": thread_id_for(delegation.identity.user_id, conversation_id)
        }
    }


def _writes_enabled(graph_instance: Any, fast_mode: bool) -> bool:
    """写工具靠 interrupt 暂停等确认，没有 checkpointer 就无法恢复，只能关掉。"""

    if fast_mode:
        return False
    return getattr(graph_instance, "checkpointer", None) is not None


async def _pending_confirmations(
    graph_instance: Any, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """读出本轮被挂起的确认请求。中断不在 astream 的 data 里，只能从状态快照拿。"""

    if getattr(graph_instance, "checkpointer", None) is None:
        return []
    snapshot = await graph_instance.aget_state(config)
    return _confirmations_from_snapshot(snapshot)


def _confirmations_from_snapshot(snapshot: Any | None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for pending in getattr(snapshot, "interrupts", ()) or ():
        value = getattr(pending, "value", None)
        interrupt_id = getattr(pending, "id", None)
        if not interrupt_id or not isinstance(value, dict) or not value.get("kind"):
            continue
        found.append({
            "id": interrupt_id,
            "kind": value.get("kind"),
            "prompt": value.get("prompt"),
            "detail": value.get("detail") or {},
        })
    return found


async def _checkpoint_snapshot(graph_instance: Any, config: dict[str, Any]) -> Any | None:
    if getattr(graph_instance, "checkpointer", None) is None:
        return None
    return await graph_instance.aget_state(config)


def _checkpoint_has_messages(snapshot: Any | None) -> bool:
    values = getattr(snapshot, "values", None)
    return isinstance(values, dict) and bool(values.get("messages"))


def _recovery_state(request: ChatRequest, delegation: DelegationContext) -> dict[str, Any]:
    """Use authoritative history only for an empty checkpoint, then append this turn."""

    return {
        "messages": build_rehydrated_messages(request.recovery_messages, request.message),
        "conversation_id": request.conversation_id,
        "patient_id": delegation.identity.patient_id,
        "long_term_memories": [
            item.model_dump(by_alias=True) for item in request.long_term_memories
        ] if request.memory_enabled else [],
    }


async def _sse_error(code: str, message: str) -> AsyncIterator[str]:
    yield _sse({"type": "error", "code": code, "message": message})


async def _confirmation_stream(
    conversation_id: str, pending: list[dict[str, Any]]
) -> AsyncIterator[str]:
    confirmation = pending[0]
    yield _sse({
        "type": "confirm",
        "conversationId": conversation_id,
        "kind": confirmation.get("kind"),
        "prompt": confirmation.get("prompt"),
        "detail": confirmation.get("detail") or {},
        "interruptId": confirmation.get("id"),
    })


def _text_from_message_chunk(message_chunk: object) -> str:
    """从 LangChain 字符串或内容块消息片段中提取文本。"""

    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        value = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if isinstance(value, str):
            text_parts.append(value)
    return "".join(text_parts)


def _is_streamable_message(message_chunk: object) -> bool:
    if not isinstance(message_chunk, (AIMessage, AIMessageChunk)):
        return False
    return not any((
        getattr(message_chunk, "tool_calls", None),
        getattr(message_chunk, "tool_call_chunks", None),
        getattr(message_chunk, "invalid_tool_calls", None),
    )) and bool(_text_from_message_chunk(message_chunk).strip())


# 单意图时直接对患者输出正文的根图节点。tool_node 的回复由嵌套 Agent 生成，
# 只在子图命名空间里产生分片，因此不在此列。
_SOLE_AGENT_STREAM_NODES = {
    "chat": "chat_node",
    "knowledge": "knowledge_node",
}


def _stream_visible_nodes(selected_agents: list[str], fast_mode: bool = False) -> set[str]:
    """选择对患者可见的图节点输出。

    起始节点也可能产生 LLM 消息，但这些是路由 JSON，绝不能发送到浏览器。
    当多个回复节点同时启用时，只有 final_node 执行最终汇总，因此它是唯一安全的流式输出节点。
    """

    # 快速模式没有路由与汇总，fast_node 直接产出面向患者的正文。
    if fast_mode:
        return {"fast_node"}

    # 只有一个回复节点被选中时，final_node 只做透传、不再调用模型，
    # 该节点自身的输出就是最终正文，可以直接流式转发。
    if len(selected_agents) == 1:
        node = _SOLE_AGENT_STREAM_NODES.get(selected_agents[0])
        if node is not None:
            return {node}
    return {"final_node"}


def _merge_stream_state(state: dict[str, Any], part: dict[str, Any]) -> None:
    """从根图的 v2 values 事件中保留最新图状态。"""

    # 嵌套 Agent 有自己的 values 流。只有根图的 values 包含此 API 所需的
    # final_reply、selected_agents 和 rag_sources。
    if part.get("ns") or part.get("type") != "values":
        return
    data = part.get("data")
    if isinstance(data, dict):
        state.update(data)


async def _stream_graph(
    graph_instance: Any,
    graph_input: Any,
    context: HospitalToolContext,
    config: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """生成 LangGraph v2 流式片段。"""

    async for part in graph_instance.astream(
        graph_input,
        context=context,
        config=config,
        stream_mode=["messages", "values"],
        subgraphs=True,
        version="v2",
    ):
        if isinstance(part, dict):
            yield part


def _sse(event: dict[str, Any]) -> str:
    """编码一条兼容浏览器的服务器发送事件，同时保留中文文本。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    file: UploadFile = File(..., description="用于构建知识库的 PDF、Word 或文本文件"),
    document_id: str | None = Query(default=None, alias="documentId", max_length=64),
    uploaded_by: int = Query(default=0, alias="uploadedBy", ge=0),
    effective_from: str | None = Query(default=None, alias="effectiveFrom", max_length=40),
    expires_at: str | None = Query(default=None, alias="expiresAt", max_length=40),
    force_rebuild: bool = Query(default=False, alias="forceRebuild"),
) -> dict[str, Any]:
    """上传文档并写入医院 RAG 知识库。"""

    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="请上传带文件名的文档")

    try:
        content = await file.read()
    finally:
        await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    try:
        lifecycle = {
            "document_id": document_id,
            "uploaded_by": uploaded_by,
            "effective_from": effective_from,
            "expires_at": expires_at,
            "force_rebuild": force_rebuild,
        }
        return await run_in_threadpool(ingest_file, content, filename, **lifecycle)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("knowledge_document_ingest_failed filename={}", filename)
        raise HTTPException(status_code=500, detail="文档写入知识库失败，请稍后再试") from exc


@router.get("/documents/{document_id}")
async def inspect_knowledge_document(document_id: str) -> dict[str, Any]:
    versions = await run_in_threadpool(get_document_versions, document_id)
    if not versions:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    return {"documentId": document_id, "versions": versions}


@router.post("/documents/{document_id}/deactivate")
async def deactivate_knowledge_document(document_id: str) -> dict[str, Any]:
    try:
        count = await run_in_threadpool(deactivate_document, document_id)
    except Exception as exc:
        logger.exception("knowledge_document_deactivate_failed document_id={}", document_id)
        raise HTTPException(status_code=500, detail="知识文档停用失败") from exc
    if count == 0:
        raise HTTPException(status_code=404, detail="没有可停用的知识文档")
    return {"documentId": document_id, "status": "inactive", "versions": count}


@router.post("/documents/{document_id}/rebuild", status_code=status.HTTP_201_CREATED)
async def rebuild_knowledge_document(
    document_id: str,
    file: UploadFile = File(...),
    uploaded_by: int = Query(default=0, alias="uploadedBy", ge=0),
    effective_from: str | None = Query(default=None, alias="effectiveFrom", max_length=40),
    expires_at: str | None = Query(default=None, alias="expiresAt", max_length=40),
) -> dict[str, Any]:
    filename = Path(file.filename or "").name
    try:
        content = await file.read()
    finally:
        await file.close()
    if not filename or not content:
        raise HTTPException(status_code=400, detail="重建文件不能为空")
    try:
        return await run_in_threadpool(
            ingest_file,
            content,
            filename,
            document_id=document_id,
            uploaded_by=uploaded_by,
            effective_from=effective_from,
            expires_at=expires_at,
            force_rebuild=True,
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("knowledge_document_rebuild_failed document_id={}", document_id)
        raise HTTPException(status_code=500, detail="知识文档重建失败") from exc


@router.delete("/documents/{document_id}")
async def delete_knowledge_document(document_id: str) -> dict[str, Any]:
    try:
        count = await run_in_threadpool(delete_document, document_id)
    except Exception as exc:
        logger.exception("knowledge_document_delete_failed document_id={}", document_id)
        raise HTTPException(status_code=500, detail="知识文档删除失败") from exc
    return {"documentId": document_id, "deletedVersions": count}


@router.delete("/memory/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_memory(
    conversation_id: str,
    user_id: int = Query(alias="userId", gt=0),
) -> Response:
    """清除单个会话的 checkpoint。会话归属由 Java 侧校验后才会调用。"""

    checkpointer = get_checkpointer()
    if checkpointer is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        # Java 已完成归属校验；userId 只用于构造隔离的 LangGraph thread key。
        await checkpointer.adelete_thread(thread_id_for(user_id, conversation_id))
    except Exception:  # noqa: BLE001 - saver backends expose heterogeneous errors
        logger.exception("conversation_memory_delete_failed conversation_id={}", conversation_id)
        raise HTTPException(status_code=500, detail="会话记忆清理失败") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _chat_events(
    *,
    graph_instance: Any,
    graph_input: Any,
    context: HospitalToolContext,
    config: dict[str, Any],
    conversation_id: str,
    fast_mode: bool,
    request_id: str | None,
    thread_id: str,
    checkpoint_hit: bool,
    rehydrated: bool,
) -> AsyncIterator[str]:
    """/stream 与 /resume 共用的 SSE 事件流。"""

    started_at = perf_counter()
    trace = begin_context_trace(
        request_id=request_id,
        thread_id=thread_id,
        mode="fast" if fast_mode else "normal",
        checkpoint_hit=checkpoint_hit,
        rehydrated=rehydrated,
    )
    first_token_at: float | None = None
    yield _sse({"type": "status", "content": "正在分析您的问题…"})
    graph_state: dict[str, Any] = {}
    streamed_reply = False
    selected_agents: list[str] = []
    retrieval_status_sent = False
    final_status_sent = False
    try:
        async for part in _stream_graph(graph_instance, graph_input, context, config):
            _merge_stream_state(graph_state, part)
            incoming_agents = graph_state.get("selected_agents") or []
            selected_agents = [
                agent for agent in incoming_agents if isinstance(agent, str)
            ]

            if not fast_mode and "knowledge" in selected_agents and not retrieval_status_sent:
                retrieval_status_sent = True
                yield _sse({"type": "status", "content": "正在检索相关资料…"})

            if part.get("type") != "messages":
                continue
            if part.get("ns"):
                # 嵌套 Agent（网页检索、业务工具）的模型分片属于实现细节，
                # 只转发根图节点自己产生的消息。
                continue
            data = part.get("data")
            if not isinstance(data, (list, tuple)) or len(data) != 2:
                continue
            message_chunk, metadata = data
            if not isinstance(metadata, dict):
                continue
            node_name = metadata.get("langgraph_node")
            visible_nodes = _stream_visible_nodes(selected_agents, fast_mode)
            if node_name not in visible_nodes or not _is_streamable_message(message_chunk):
                continue
            content = _text_from_message_chunk(message_chunk)
            if not fast_mode and "knowledge" in selected_agents and not final_status_sent:
                final_status_sent = True
                yield _sse({"type": "status", "content": "正在整理答案…"})
            if first_token_at is None:
                first_token_at = perf_counter()
                trace.first_token_ms = round((first_token_at - started_at) * 1000)
                logger.info(
                    "chat_stream_first_token conversation_id={} elapsed_ms={}",
                    conversation_id,
                    round((first_token_at - started_at) * 1000),
                )
            streamed_reply = True
            yield _sse({"type": "token", "content": content})

        # 写工具挂起时根图不会产出 final_reply，必须在取回复之前先判断有没有待确认项。
        pending = await _pending_confirmations(graph_instance, config)
        if pending:
            confirmation = pending[0]
            logger.info(
                "chat_stream_awaiting_confirmation conversation_id={} kind={} interrupt_id={} pending_count={}",
                conversation_id,
                confirmation.get("kind"),
                confirmation.get("id"),
                len(pending),
            )
            yield _sse({
                "type": "confirm",
                "conversationId": conversation_id,
                "kind": confirmation.get("kind"),
                "prompt": confirmation.get("prompt"),
                "detail": confirmation.get("detail") or {},
                "interruptId": confirmation.get("id"),
            })
            trace.finish()
            return

        response = _response_from_state(conversation_id, graph_state)
    except HTTPException as exc:
        yield _sse({
            "type": "error",
            "code": "AI_CHAT_FAILED",
            "message": str(exc.detail),
        })
        trace.finish(error_code="AI_CHAT_FAILED")
        return
    except asyncio.CancelledError:
        logger.info("chat_stream_cancelled conversation_id={}", conversation_id)
        trace.finish(error_code="AI_STREAM_CANCELLED")
        raise
    except Exception:  # noqa: BLE001 - stream boundary maps provider failures to SSE
        logger.exception("chat_stream_failed conversation_id={}", conversation_id)
        yield _sse({
            "type": "error",
            "code": "AI_CHAT_FAILED",
            "message": "AI 对话处理失败，请稍后再试",
        })
        trace.finish(error_code="AI_CHAT_FAILED")
        return

    for source in response.sources:
        yield _sse({"type": "citation", "sources": [source]})
    if not streamed_reply:
        # 如果服务提供方不提供令牌片段，则发送一个完整令牌以保持协议一致，
        # 避免返回空答案。
        yield _sse({"type": "token", "content": response.reply})
    yield _sse({
        "type": "done",
        **response.model_dump(by_alias=True),
    })
    logger.info(
        "chat_stream_completed conversation_id={} elapsed_ms={} first_token_ms={}",
        conversation_id,
        round((perf_counter() - started_at) * 1000),
        round((first_token_at - started_at) * 1000) if first_token_at is not None else None,
    )
    trace.finish()


def _event_stream(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> StreamingResponse:
    """运行对话图，并通过 SSE 暴露增量模型输出。"""

    _assert_request_identity(request, delegation)
    graph_instance = _graph_for(request.memory_enabled, request.fast_mode)
    writes_enabled = _writes_enabled(graph_instance, request.fast_mode)
    config = _graph_config(request.conversation_id, delegation)
    has_checkpointer = getattr(graph_instance, "checkpointer", None) is not None
    snapshot = await _checkpoint_snapshot(graph_instance, config)
    checkpoint_hit = _checkpoint_has_messages(snapshot)
    if has_checkpointer:
        pending = _confirmations_from_snapshot(snapshot)
        if pending:
            logger.info(
                "chat_stream_preserved_pending_confirmation conversation_id={} pending_count={} ids={}",
                request.conversation_id,
                len(pending),
                [item.get("id") for item in pending],
            )
            trace = begin_context_trace(
                request_id=current_request_id(),
                thread_id=config["configurable"]["thread_id"],
                mode="normal",
                checkpoint_hit=True,
                rehydrated=False,
            )
            trace.node_names.add("pending_confirmation")
            trace.finish()
            return _event_stream(_confirmation_stream(request.conversation_id, pending))

    graph_input = _initial_state(request, delegation)
    rehydrated = False
    if has_checkpointer and not checkpoint_hit and request.recovery_messages:
        graph_input = _recovery_state(request, delegation)
        rehydrated = True
        logger.info(
            "chat_checkpoint_rehydrated conversation_id={} message_count={}",
            request.conversation_id,
            len(request.recovery_messages),
        )
    return _event_stream(_chat_events(
        graph_instance=graph_instance,
        graph_input=graph_input,
        context=_runtime_context(
            request.conversation_id, delegation, writes_enabled=writes_enabled
        ),
        config=config,
        conversation_id=request.conversation_id,
        fast_mode=request.fast_mode,
        request_id=current_request_id(),
        thread_id=config["configurable"]["thread_id"],
        checkpoint_hit=checkpoint_hit,
        rehydrated=rehydrated,
    ))


@router.post("/resume")
async def chat_resume(
    request: ChatResumeRequest,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> StreamingResponse:
    """患者在确认卡片上作出选择后，续跑同一个 thread 上被挂起的那一轮。"""

    _assert_request_identity(request, delegation)
    # 恢复必须落在带 checkpointer 的正常图上：快速模式没有写工具，无记忆图无从恢复。
    graph_instance = _graph_for(memory_enabled=True, fast_mode=False)
    if getattr(graph_instance, "checkpointer", None) is None:
        raise HTTPException(status_code=409, detail="会话已过期，请重新发起办理")

    config = _graph_config(request.conversation_id, delegation)
    pending = await _pending_confirmations(graph_instance, config)
    logger.info(
        "chat_resume_pending conversation_id={} pending_count={} ids={} kinds={} interrupt_id={}",
        request.conversation_id,
        len(pending),
        [item.get("id") for item in pending],
        [item.get("kind") for item in pending],
        request.interrupt_id,
    )
    command, error_code, error_message = _resume_command(
        request.decision, request.interrupt_id, pending
    )
    if command is None:
        trace = begin_context_trace(
            request_id=current_request_id(),
            thread_id=config["configurable"]["thread_id"],
            mode="normal",
            checkpoint_hit=bool(pending),
            rehydrated=False,
        )
        trace.node_names.add("resume_validation")
        trace.finish(error_code=error_code or "AI_RESUME_STALE")
        return _event_stream(_sse_error(error_code or "AI_RESUME_STALE", error_message or "请重新发起挂号"))

    return _event_stream(_chat_events(
        graph_instance=graph_instance,
        graph_input=command,
        context=_runtime_context(
            request.conversation_id, delegation, writes_enabled=True
        ),
        config=config,
        conversation_id=request.conversation_id,
        fast_mode=False,
        request_id=current_request_id(),
        thread_id=config["configurable"]["thread_id"],
        checkpoint_hit=True,
        rehydrated=False,
    ))
