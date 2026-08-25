import json
import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from loguru import logger
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from app.api.dependencies.auth import verify_api_key
from app.graphs.hospital.graphs import graph
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"],
    dependencies=[Depends(verify_api_key)],
)


async def _run_chat(request: ChatRequest) -> ChatResponse:
    """执行医院对话图，并返回本轮的最终回复和 RAG 来源。"""
    initial_state = _initial_state(request)

    try:
        # 图中的检索和模型调用均为同步 I/O，放到工作线程避免阻塞 FastAPI 事件循环。
        result = await run_in_threadpool(graph.invoke, initial_state)
    except Exception as exc:
        logger.exception("chat_graph_failed conversation_id={}", request.conversation_id)
        raise HTTPException(status_code=500, detail="AI 对话处理失败，请稍后再试") from exc

    return _response_from_state(request, result)


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


def _text_from_message_chunk(message_chunk: object) -> str:
    """Extract text from LangChain string or content-block message chunks."""

    content = getattr(message_chunk, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            value = block.get("text")
        else:
            value = getattr(block, "text", None)
        if isinstance(value, str):
            text_parts.append(value)
    return "".join(text_parts)


def _is_streamable_message(message_chunk: object) -> bool:
    """Return whether a graph message is safe to expose as patient-facing text.

    LangGraph can surface messages emitted by nested agents while streaming. A
    knowledge agent may produce tool results, routing messages, and tool-call
    requests before it produces its final answer. Only assistant text is part of
    the public SSE contract; everything else is internal graph state.
    """

    if not isinstance(message_chunk, (AIMessage, AIMessageChunk)):
        return False
    if getattr(message_chunk, "tool_calls", None):
        return False
    if getattr(message_chunk, "tool_call_chunks", None):
        return False
    if getattr(message_chunk, "invalid_tool_calls", None):
        return False
    return bool(_text_from_message_chunk(message_chunk).strip())


def _stream_visible_nodes(selected_agents: list[str]) -> set[str]:
    """Choose the graph node whose output is visible to the patient.

    The begin node may also emit LLM messages, but those are routing JSON and must
    never be sent to the browser. When multiple reply-producing nodes are active,
    final_node is the only safe stream because it performs the final merge.
    """

    # Knowledge agents may invoke RAG and web-search tools. Their nested model
    # messages are implementation details, so knowledge requests must wait for
    # the graph's final merge. Chat-only requests have no retrieval/tool phase
    # and can continue to stream directly from the chat node.
    if selected_agents == ["chat"]:
        return {"chat_node"}
    return {"final_node"}


def _is_visible_message_node(
    node_name: object,
    namespace: object,
    visible_nodes: set[str],
) -> bool:
    """Match only the visible node or its explicitly allowed model subgraph."""

    if isinstance(node_name, str) and node_name in visible_nodes:
        return True

    if not isinstance(namespace, (list, tuple)):
        return False

    # A chat/final node may contain a nested model invocation. Only the first
    # namespace segment grants visibility; deeper siblings such as tools under a
    # knowledge node must never inherit it.
    first_segment = namespace[0] if namespace else None
    if not isinstance(first_segment, str):
        return False
    first_node = first_segment.split(":", 1)[0]
    return first_node in visible_nodes


def _merge_stream_state(state: dict[str, Any], part: dict[str, Any]) -> None:
    """Keep the latest graph state from v2 values or merge v2 updates."""

    # Nested agents have their own values stream. Only the root graph values
    # contain final_reply, selected_agents and rag_sources for this API.
    if part.get("ns"):
        return
    part_type = part.get("type")
    data = part.get("data")
    if part_type == "values" and isinstance(data, dict):
        state.update(data)
        return
    if part_type != "updates" or not isinstance(data, dict):
        return
    for update in data.values():
        if isinstance(update, dict):
            state.update(update)


async def _stream_graph(request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
    """Yield LangGraph v2 stream parts, with a compatibility fallback for tests."""

    initial_state = _initial_state(request)
    astream = getattr(graph, "astream", None)
    if astream is None:
        # Older/fake graph implementations can still exercise the HTTP contract.
        result = await run_in_threadpool(graph.invoke, initial_state)
        yield {"type": "values", "data": result}
        return

    async for part in astream(
        initial_state,
        stream_mode=["messages", "values"],
        subgraphs=True,
        version="v2",
    ):
        if isinstance(part, dict):
            yield part


def _sse(event: dict[str, Any]) -> str:
    """Encode one browser-compatible Server-Sent Event without losing Chinese text."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Run the graph and expose incremental model output through SSE."""

    async def events() -> AsyncIterator[str]:
        yield _sse({"type": "status", "content": "正在分析您的问题…"})
        graph_state: dict[str, Any] = {}
        streamed_reply = False
        selected_agents: list[str] = []
        retrieval_status_sent = False
        final_status_sent = False
        try:
            async for part in _stream_graph(request):
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
                data = part.get("data")
                if not isinstance(data, (list, tuple)) or len(data) != 2:
                    continue
                message_chunk, metadata = data
                if not isinstance(metadata, dict):
                    continue
                node_name = metadata.get("langgraph_node") or metadata.get("node")
                visible_nodes = _stream_visible_nodes(selected_agents)
                namespace = part.get("ns") or ()
                if not _is_visible_message_node(node_name, namespace, visible_nodes):
                    continue
                if not _is_streamable_message(message_chunk):
                    continue
                content = _text_from_message_chunk(message_chunk)
                if content:
                    if "knowledge" in selected_agents and not final_status_sent:
                        final_status_sent = True
                        yield _sse({"type": "status", "content": "正在整理答案…"})
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
            # If a provider does not expose token chunks, preserve the contract by
            # sending one complete token rather than returning an empty answer.
            yield _sse({"type": "token", "content": response.reply})
        yield _sse({
            "type": "done",
            **response.model_dump(by_alias=True),
        })

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
