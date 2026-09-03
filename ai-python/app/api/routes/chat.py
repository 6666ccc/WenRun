import asyncio
import json
from time import perf_counter
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from loguru import logger
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response, StreamingResponse

from app.api.dependencies.auth import DelegationContext, verify_api_key, verify_delegation_token
from app.core.logging import current_request_id
from app.graphs.hospital.checkpointing import (
    get_checkpointer,
    get_fast_memory_graph,
    get_memory_graph,
)
from app.graphs.hospital.graphs import fast_graph, graph
from app.graphs.hospital.tools.context import HospitalToolContext
from app.models.chat import ChatRequest, ChatResponse
from app.rag.ingest import ingest_file

router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)


def _response_from_state(request: ChatRequest, result: dict[str, Any]) -> ChatResponse:
    reply = result.get("final_reply")
    if not isinstance(reply, str) or not reply.strip():
        logger.error("chat_graph_missing_final_reply conversation_id={}", request.conversation_id)
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
        conversation_id=request.conversation_id,
        selected_agents=selected_agents,
        sources=sources,
    )


def _initial_state(request: ChatRequest) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=request.message)],
        "conversation_id": request.conversation_id,
        "patient_id": request.user_context.patient_id,
    }


def _runtime_context(delegation: DelegationContext) -> HospitalToolContext:
    """委托令牌与追踪号只在本次请求内有效，绝不进入持久化 State。"""

    return HospitalToolContext(delegation.token, current_request_id())


def _graph_for(memory_enabled: bool, fast_mode: bool):
    if memory_enabled:
        memory_graph = get_fast_memory_graph() if fast_mode else get_memory_graph()
        if memory_graph is not None:
            return memory_graph
    return fast_graph if fast_mode else graph


def _graph_config(request: ChatRequest) -> dict[str, Any]:
    return {"configurable": {"thread_id": request.conversation_id}}


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
    request: ChatRequest, delegation: DelegationContext
) -> AsyncIterator[dict[str, Any]]:
    """生成 LangGraph v2 流式片段。"""

    async for part in _graph_for(request.memory_enabled, request.fast_mode).astream(
        _initial_state(request),
        context=_runtime_context(delegation),
        config=_graph_config(request),
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
) -> dict[str, str | int]:
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
        return await run_in_threadpool(ingest_file, content, filename)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("knowledge_document_ingest_failed filename={}", filename)
        raise HTTPException(status_code=500, detail="文档写入知识库失败，请稍后再试") from exc


@router.delete("/memory/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_memory(conversation_id: str) -> Response:
    """清除单个会话的 checkpoint。会话归属由 Java 侧校验后才会调用。"""

    checkpointer = get_checkpointer()
    if checkpointer is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        await checkpointer.adelete_thread(conversation_id)
    except Exception:
        logger.exception("conversation_memory_delete_failed conversation_id={}", conversation_id)
        raise HTTPException(status_code=500, detail="会话记忆清理失败") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> StreamingResponse:
    """运行对话图，并通过 SSE 暴露增量模型输出。"""

    async def events() -> AsyncIterator[str]:
        started_at = perf_counter()
        first_token_at: float | None = None
        yield _sse({"type": "status", "content": "正在分析您的问题…"})
        graph_state: dict[str, Any] = {}
        streamed_reply = False
        selected_agents: list[str] = []
        retrieval_status_sent = False
        final_status_sent = False
        try:
            async for part in _stream_graph(request, delegation):
                _merge_stream_state(graph_state, part)
                incoming_agents = graph_state.get("selected_agents") or []
                selected_agents = [
                    agent for agent in incoming_agents if isinstance(agent, str)
                ]

                if "knowledge" in selected_agents and not retrieval_status_sent:
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
                visible_nodes = _stream_visible_nodes(selected_agents, request.fast_mode)
                if node_name not in visible_nodes or not _is_streamable_message(message_chunk):
                    continue
                content = _text_from_message_chunk(message_chunk)
                if "knowledge" in selected_agents and not final_status_sent:
                    final_status_sent = True
                    yield _sse({"type": "status", "content": "正在整理答案…"})
                if first_token_at is None:
                    first_token_at = perf_counter()
                    logger.info(
                        "chat_stream_first_token conversation_id={} elapsed_ms={}",
                        request.conversation_id,
                        round((first_token_at - started_at) * 1000),
                    )
                streamed_reply = True
                yield _sse({"type": "token", "content": content})

            response = _response_from_state(request, graph_state)
        except HTTPException as exc:
            yield _sse({
                "type": "error",
                "code": "AI_CHAT_FAILED",
                "message": str(exc.detail),
            })
            return
        except asyncio.CancelledError:
            logger.info("chat_stream_cancelled conversation_id={}", request.conversation_id)
            raise
        except Exception:
            logger.exception("chat_stream_failed conversation_id={}", request.conversation_id)
            yield _sse({
                "type": "error",
                "code": "AI_CHAT_FAILED",
                "message": "AI 对话处理失败，请稍后再试",
            })
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
            request.conversation_id,
            round((perf_counter() - started_at) * 1000),
            round((first_token_at - started_at) * 1000) if first_token_at is not None else None,
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
