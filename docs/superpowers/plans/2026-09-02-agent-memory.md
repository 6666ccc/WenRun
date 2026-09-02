# Agent 会话记忆实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给医院对话 Agent 加上真正的会话记忆——同一 `conversationId` 内多轮上下文连续、断线刷新后可恢复，并在长会话时自动压缩历史。

**Architecture:** 用 LangGraph Redis checkpointer 做线程级持久化，`thread_id` 取 `conversationId`。落地前必须先把请求级委托令牌从 State 迁到 Runtime Context（否则凭证会被写进可恢复的 checkpoint），并给每个回合加字段重置（否则上一轮的节点产出会跨轮泄漏到本轮汇总）。长会话由一个位于 `final_node` 之后的摘要节点压缩，并用 `RemoveMessage` 裁剪历史，把 checkpoint 体积控制在低配 Redis 的预算内。

**Tech Stack:** Python 3.11+ / FastAPI / LangGraph 1.2.10 / langchain 1.3.14 / langgraph-checkpoint 4.1.1 / langgraph-checkpoint-redis 0.5.2 / Redis 8（自带 JSON + Query Engine）/ pytest + pytest-asyncio

## Global Constraints

- 委托令牌（`delegated_token`）**禁止**出现在任何持久化 State 或 checkpoint 中，只能走 Runtime Context。
- `langgraph-checkpoint-redis` 要求 Redis 带 RedisJSON 与 RediSearch 模块。`redis:7-alpine` **不满足**，必须用 `redis:8-alpine` 或更高（Redis 8 已把两者收进内核）。
- checkpoint 与 Java 登录 Session 必须使用不同的 Redis 逻辑 DB：Session 用 `db=0`，checkpoint 用 `db=1`。
- 生产 Redis 的 `maxmemory-policy` 保持 `allkeys-lru`，因此 checkpoint 必须设 TTL 且使用 Shallow saver（每 thread 只留最新 checkpoint），不得使用完整版 `AsyncRedisSaver`。
- Python 侧 Redis 环境变量统一命名 `AI_REDIS_URL`，不复用 Java 的 `SPRING_DATA_REDIS_*`。
- 图的模块级 `graph` 变量必须保留（`ai-python/langgraph.json` 里 `"hospital": "./app/graphs/hospital/graphs.py:graph"` 依赖它），且该实例**不带** checkpointer。
- 上下文窗口常量只允许有一个来源：`app/graphs/hospital/memory.py`。禁止在节点里再写 `[-6:]` 这类裸切片。
- 所有新增/修改的测试必须用 `python -m pytest` 在 `ai-python` 目录下跑通，不得引入真实 Redis、真实 Qdrant 或真实 LLM 调用。
- 现有测试用 `TestClient(create_app())`（非 `with` 语法），因此 FastAPI lifespan 不会执行、`get_memory_graph()` 返回 `None`、自动回落到无记忆图。**不要**为了记忆功能把这些测试改成 `with TestClient(...)`。

---

## File Structure

**新建：**

| 文件 | 职责 |
|---|---|
| `ai-python/app/graphs/hospital/memory.py` | 记忆策略：回合字段重置、上下文窗口、摘要触发判断与消息切分 |
| `ai-python/app/graphs/hospital/checkpointing.py` | Redis checkpointer 生命周期 + 带记忆图的注册表 |
| `ai-python/app/graphs/hospital/nodes/summarize.py` | 摘要节点 |
| `ai-python/tests/unit/test_memory.py` | 记忆策略单元测试 |
| `ai-python/tests/unit/test_turn_isolation.py` | 跨轮串轮回归测试（本计划最关键的测试） |
| `ai-python/tests/unit/test_checkpointing.py` | 图工厂与记忆图注册表测试 |

**修改：**

| 文件 | 改动 |
|---|---|
| `ai-python/app/graphs/hospital/state.py` | 删 `delegated_token`、`request_id`；加 `summary` |
| `ai-python/app/graphs/hospital/graphs.py` | 改为 `build_graph()` 工厂 + `context_schema` + 摘要节点 |
| `ai-python/app/graphs/hospital/nodes/tool.py` | 从 Runtime Context 取令牌 |
| `ai-python/app/graphs/hospital/nodes/begin.py` | 回合重置 + 统一窗口 |
| `ai-python/app/graphs/hospital/nodes/knowledge.py` | 统一窗口（两处） |
| `ai-python/app/graphs/hospital/nodes/chat.py` | 统一窗口 |
| `ai-python/app/api/routes/chat.py` | 传 context 与 thread_id、选图、记忆清理接口 |
| `ai-python/app/core/config.py` | 加 `redis_url`、`checkpoint_ttl_minutes` |
| `ai-python/app/main.py` | 加 lifespan |
| `ai-python/pyproject.toml` | 加 Redis checkpointer 依赖 |
| `ai-python/.env.example`、根 `.env.example` | 补 Redis 变量 |
| `ai-python/tests/test_app.py` | FakeGraph 签名补 `context`/`config` |
| `ai-python/tests/unit/test_tool_node.py` | 改为构造 `Runtime` |
| `backend-java/.../ai/service/aiService.java` | 加 `deleteConversationMemory` |
| `backend-java/.../ai/controller/aiController.java` | 删会话时级联清记忆 |
| `docker-compose.prod.yml`、`docker-compose.yml` | Redis 8 + 内存预算 + Python 侧 Redis 环境变量 |
| `docs/AI模块开发与运维指南.md`、`docs/求职项目评估与流程图.md`、`TODO.md` | 文档与实现对齐 |

**注：** 会话归属校验**无需新增**。`aiController.prepare()` 已经调用 `ownershipService.establishIfAbsent(conversationId, userId)`，且 Java 在转发前就写入了 user 消息，因此任何存在 checkpoint 的 `conversationId` 必然已在 `chat_messages` 里建立归属，换 ID 读别人记忆会被 403 拦掉。本计划不重复实现。

---

## Task 1: 委托令牌迁出 State，改用 Runtime Context

这是加 checkpointer 的硬前置：`delegated_token` 现在是 State 字段，一旦持久化就等于把短期写权限 JWT 落盘。本任务零功能变化。

复用已有的 `HospitalToolContext`（`app/graphs/hospital/tools/context.py:22-26`）作为图级 context schema——它已经带了 `delegated_token`、`request_id`、`now` 三个请求级字段，且文件顶部注释已声明「禁止写入持久化 checkpoint」。

**Files:**
- Modify: `ai-python/app/graphs/hospital/state.py:10-20`
- Modify: `ai-python/app/graphs/hospital/graphs.py:9`
- Modify: `ai-python/app/graphs/hospital/nodes/tool.py:1-16,73-102`
- Modify: `ai-python/app/api/routes/chat.py:13-17,50-59,150-163`
- Test: `ai-python/tests/unit/test_tool_node.py`
- Test: `ai-python/tests/test_app.py:133-135,177-181,247-248`

**Interfaces:**
- Produces: `HospitalToolContext(delegated_token: str, request_id: str | None = None, now: datetime = clinic_now())` 成为图的 `context_schema`；`tool_node(state: State, runtime: Runtime[HospitalToolContext]) -> dict`；`chat.py::_initial_state(request: ChatRequest) -> dict[str, Any]`（不再接收 `delegation` 参数）；`chat.py::_runtime_context(delegation: DelegationContext) -> HospitalToolContext`。
- Consumes: 无（首个任务）。

- [ ] **Step 1: 改写 `test_tool_node.py`，让 tool_node 从 Runtime 取令牌（失败测试）**

把文件里 `_tool_runtime` 之外再加一个图级 runtime 构造器，并替换两个直接往 state 里塞 `delegated_token` 的测试。

在 import 区加入：

```python
from langgraph.runtime import Runtime
```

替换 `test_tool_node_skips_when_tools_not_selected`、`test_tool_node_invokes_agent_with_request_scoped_context`、`test_tool_node_returns_unavailable_when_delegated_token_missing` 三个测试为：

```python
def _graph_runtime(context: HospitalToolContext) -> Runtime:
    return Runtime(context=context)


def test_tool_node_skips_when_tools_not_selected():
    assert tool_node_module.tool_node(
        {"selected_agents": ["chat"]}, _graph_runtime(CONTEXT)
    ) == {}


def test_tool_node_invokes_agent_with_request_scoped_context(monkeypatch):
    captured: dict = {}

    class FakeAgent:
        def invoke(self, payload, *, context):
            captured["messages"] = payload["messages"]
            captured["context"] = context
            return {"messages": [HumanMessage(content="当前可查询的科室：内科、儿科。")]}

    monkeypatch.setattr(tool_node_module, "agent", FakeAgent())

    history = [HumanMessage(content="有哪些科室？")]
    result = tool_node_module.tool_node(
        {
            "selected_agents": ["tools"],
            "conversation_id": "conversation-1",
            "messages": history,
        },
        _graph_runtime(CONTEXT),
    )

    assert result == {"tools_reply": "当前可查询的科室：内科、儿科。"}
    assert captured["messages"] == history
    assert captured["context"] is CONTEXT
    assert captured["context"].now.tzinfo == CLINIC_TZ


def test_tool_node_returns_unavailable_when_delegated_token_missing():
    assert tool_node_module.tool_node(
        {
            "selected_agents": ["tools"],
            "messages": [HumanMessage(content="有哪些科室？")],
        },
        _graph_runtime(HospitalToolContext("", "trace-123", now=FROZEN_NOW)),
    ) == {"tools_reply": "业务查询服务暂不可用，请稍后重试。"}
```

再加一条新测试，锁死「State 里不能有令牌」：

```python
def test_state_schema_never_carries_delegated_token():
    from app.graphs.hospital.state import State

    assert "delegated_token" not in State.__annotations__
    assert "request_id" not in State.__annotations__
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_tool_node.py -v`
Expected: FAIL —— `tool_node() takes 1 positional argument but 2 were given`，以及 `test_state_schema_never_carries_delegated_token` 断言失败。

- [ ] **Step 3: 从 State 删除请求级字段**

`ai-python/app/graphs/hospital/state.py` 全文改为：

```python
from typing import Literal

from langgraph.graph import MessagesState

AgentName = Literal["knowledge", "chat", "tools"]

"""节点，主要还是意图判断，以及后续的节点选择"""


class State(MessagesState):
    conversation_id: str  # 会话id，同时作为 checkpointer 的 thread_id
    patient_id: int | None  # 患者id
    selected_agents: list[AgentName]  # begin 节点从 IntentDecision 写入，可多选
    knowledge_reply: str | None  # 知识节点写入
    rag_sources: list[dict] | None  # RAG 命中的资料来源，供最终响应展示引用
    chat_reply: str | None  # 闲聊节点写入，用户闲聊
    tools_reply: str | None  # 工具节点写入，用户选择工具
    final_reply: str | None  # 汇总节点写入，最终回复
```

- [ ] **Step 4: 给图声明 context_schema**

`ai-python/app/graphs/hospital/graphs.py` 第 7-9 行，import 区补一行并改 `StateGraph` 构造：

```python
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.context import HospitalToolContext
from langgraph.graph import END, START, StateGraph

workflow = StateGraph(State, context_schema=HospitalToolContext)
```

- [ ] **Step 5: tool_node 改从 Runtime Context 取令牌**

`ai-python/app/graphs/hospital/nodes/tool.py`：import 区把 `clinic_now` 去掉（不再使用）、加 `Runtime`：

```python
from app.graphs.hospital.tools.context import format_clinic_clock
from app.models.chat import model
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langgraph.runtime import Runtime
from loguru import logger
```

函数体（第 73-102 行）改为：

```python
def tool_node(state: State, runtime: Runtime[HospitalToolContext]) -> dict:
    ##任务一：看起始节点是否把 tools 写进 selected_agents
    selected = state.get("selected_agents") or []
    if "tools" not in selected:
        return {}

    ##任务二：没有委托令牌就不要打扰模型，直接给出降级回复
    context = runtime.context
    delegated_token = getattr(context, "delegated_token", "")
    if not isinstance(delegated_token, str) or not delegated_token.strip():
        logger.error(
            "tool_node_missing_delegated_token conversation_id={}",
            state.get("conversation_id"),
        )
        return {"tools_reply": "业务查询服务暂不可用，请稍后重试。"}

    ##任务三：运行时上下文只在本次请求内有效，直接透传给嵌套 Agent
    result = agent.invoke(
        {"messages": list(state.get("messages") or [])[-6:]},
        context=context,
    )
    messages = result.get("messages") or []
    last = messages[-1] if messages else None
    content = getattr(last, "content", "") if last is not None else ""
    if not isinstance(content, str):
        content = str(content)
    return {"tools_reply": content}
```

注意 `HospitalToolContext` 已在该文件第 5-11 行的 `from app.graphs.hospital.tools import (...)` 里导入，不需要重复导入。

- [ ] **Step 6: 运行 tool_node 测试确认通过**

Run: `python -m pytest tests/unit/test_tool_node.py -v`
Expected: PASS，共 8 条。

- [ ] **Step 7: chat 路由改为传 Runtime Context**

`ai-python/app/api/routes/chat.py`，import 区补一行：

```python
from app.graphs.hospital.tools.context import HospitalToolContext
```

第 50-59 行 `_initial_state` 与第 150-163 行 `_stream_graph` 改为：

```python
def _initial_state(request: ChatRequest) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=request.message)],
        "conversation_id": request.conversation_id,
        "patient_id": request.user_context.patient_id,
    }


def _runtime_context(delegation: DelegationContext) -> HospitalToolContext:
    """委托令牌与追踪号只在本次请求内有效，绝不进入持久化 State。"""

    return HospitalToolContext(delegation.token, current_request_id())
```

```python
async def _stream_graph(
    request: ChatRequest, delegation: DelegationContext
) -> AsyncIterator[dict[str, Any]]:
    """生成 LangGraph v2 流式片段。"""

    async for part in graph.astream(
        _initial_state(request),
        context=_runtime_context(delegation),
        stream_mode=["messages", "values"],
        subgraphs=True,
        version="v2",
    ):
        if isinstance(part, dict):
            yield part
```

- [ ] **Step 8: 更新 test_app.py 的三个 FakeGraph 签名**

`ai-python/tests/test_app.py` 里三处 `async def astream(self, state, *, stream_mode, subgraphs, version):` 全部改为：

```python
        async def astream(self, state, *, context, stream_mode, subgraphs, version):
```

在 `test_chat_stream_uses_frontend_sse_contract` 里 `captured["state"]` 之后加一行 `captured["context"] = context`，并在断言区补上：

```python
    assert captured["context"].delegated_token
    assert "delegated_token" not in captured["state"]
```

- [ ] **Step 9: 全量测试**

Run: `python -m pytest -q`
Expected: PASS，无 FAILED、无 ERROR。

- [ ] **Step 10: 提交**

```bash
git add ai-python/app/graphs/hospital/state.py ai-python/app/graphs/hospital/graphs.py ai-python/app/graphs/hospital/nodes/tool.py ai-python/app/api/routes/chat.py ai-python/tests/unit/test_tool_node.py ai-python/tests/test_app.py
git commit -m "refactor(ai): 委托令牌从图 State 迁到 Runtime Context"
```

---

## Task 2: 回合字段重置与统一上下文窗口

State 持久化后，`knowledge_node`/`chat_node`/`tool_node` 未被选中时的 `return {}` 会让上一轮的 `knowledge_reply` 等字段存活到本轮，被 `final_node._collect_replies`（`nodes/final.py:34-41`）当成本轮结果一起汇总。本任务在加 checkpointer **之前**修掉，并把散在四处的 `[-6:]` 收敬到单一来源。

**Files:**
- Create: `ai-python/app/graphs/hospital/memory.py`
- Create: `ai-python/tests/unit/test_memory.py`
- Modify: `ai-python/app/graphs/hospital/nodes/begin.py:1-7,188-211`
- Modify: `ai-python/app/graphs/hospital/nodes/knowledge.py:110-111,159`
- Modify: `ai-python/app/graphs/hospital/nodes/chat.py:47`
- Modify: `ai-python/app/graphs/hospital/nodes/tool.py:90`
- Test: `ai-python/tests/unit/test_begin_node.py`

**Interfaces:**
- Consumes: Task 1 的 `State`（已无 `delegated_token`/`request_id`）。
- Produces: `memory.RECENT_MESSAGE_WINDOW: int = 6`；`memory.TURN_SCOPED_REPLY_FIELDS: tuple[str, ...]`；`memory.reset_turn_fields() -> dict[str, None]`；`memory.recent_messages(state: State, limit: int = RECENT_MESSAGE_WINDOW) -> list[BaseMessage]`。Task 5 会扩展 `recent_messages` 以拼入摘要，签名不变。

- [ ] **Step 1: 写失败测试**

创建 `ai-python/tests/unit/test_memory.py`：

```python
import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain_core.messages import AIMessage, HumanMessage

from app.graphs.hospital import memory


def test_reset_turn_fields_clears_every_node_output():
    assert memory.reset_turn_fields() == {
        "knowledge_reply": None,
        "rag_sources": None,
        "chat_reply": None,
        "tools_reply": None,
        "final_reply": None,
    }


def test_recent_messages_keeps_only_the_tail_window():
    history = [HumanMessage(content=str(index)) for index in range(10)]

    assert memory.recent_messages({"messages": history}) == history[-6:]


def test_recent_messages_tolerates_empty_state():
    assert memory.recent_messages({}) == []
    assert memory.recent_messages({"messages": None}) == []


def test_recent_messages_honours_explicit_limit():
    history = [HumanMessage(content="q"), AIMessage(content="a")]

    assert memory.recent_messages({"messages": history}, limit=1) == [history[-1]]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_memory.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.graphs.hospital.memory'`

- [ ] **Step 3: 创建 memory 模块**

创建 `ai-python/app/graphs/hospital/memory.py`：

```python
"""会话记忆策略：回合字段重置与统一上下文窗口。

图接上 checkpointer 后，State 会跨轮存活。节点未被选中时返回空字典，
上一轮的产出就会被 final_node 当成本轮结果一起汇总，所以每轮开头必须显式清零。
"""

from langchain_core.messages import BaseMessage

from app.graphs.hospital.state import State

# 根图的 messages 是干净的 Human/AI 交替列表（嵌套 Agent 用 invoke 调用，
# 工具消息不会写回根 State），因此 6 条约等于 3 轮问答。
RECENT_MESSAGE_WINDOW = 6

# 这些字段都只在单个回合内有意义，必须由 begin_node 在每轮开头清零。
TURN_SCOPED_REPLY_FIELDS = (
    "knowledge_reply",
    "rag_sources",
    "chat_reply",
    "tools_reply",
    "final_reply",
)


def reset_turn_fields() -> dict[str, None]:
    """清空上一轮遗留的节点产出，避免 checkpoint 恢复后串轮。"""

    return {field: None for field in TURN_SCOPED_REPLY_FIELDS}


def recent_messages(
    state: State, limit: int = RECENT_MESSAGE_WINDOW
) -> list[BaseMessage]:
    """所有节点唯一的上下文窗口来源。"""

    return list(state.get("messages") or [])[-limit:]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_memory.py -v`
Expected: PASS，共 4 条。

- [ ] **Step 5: 把 test_begin_node.py 的全等断言改成按键断言**

`begin_node` 的返回值即将多出 5 个重置字段，现有 7 处 `assert result == {"selected_agents": [...]}` 会全部失败。逐条改为按键断言（模块导入别名是 `begin`，`HumanMessage` 已在第 1 行导入）：

| 行号 | 原断言 | 改为 |
|---|---|---|
| 33 | `assert result == {"selected_agents": ["knowledge", "tools"]}` | `assert result["selected_agents"] == ["knowledge", "tools"]` |
| 50 | `assert result == {"selected_agents": ["knowledge"]}` | `assert result["selected_agents"] == ["knowledge"]` |
| 64 | `assert result == {"selected_agents": ["chat"]}` | `assert result["selected_agents"] == ["chat"]` |
| 76 | `assert result == {"selected_agents": ["chat"]}` | `assert result["selected_agents"] == ["chat"]` |
| 88 | `assert result == {"selected_agents": ["tools"]}` | `assert result["selected_agents"] == ["tools"]` |
| 111 | `assert result == {"selected_agents": ["knowledge"]}` | `assert result["selected_agents"] == ["knowledge"]` |
| 122 | `assert result == {"selected_agents": ["tools"]}` | `assert result["selected_agents"] == ["tools"]` |

第 100 行已经是按键断言，不用动。

再在文件末尾追加重置的失败测试：

```python
def test_begin_node_resets_previous_turn_outputs(monkeypatch):
    stub_model = StubModel([AIMessage(content='{"selected_agents":["chat"]}')])
    monkeypatch.setattr(begin, "model", stub_model)

    result = begin.begin_node(
        {
            "messages": [HumanMessage(content="谢谢你啊")],
            "knowledge_reply": "上一轮的用药建议",
            "rag_sources": [{"id": "S1"}],
            "tools_reply": "上一轮的号源结果",
            "final_reply": "上一轮的最终回复",
        }
    )

    assert result["selected_agents"] == ["chat"]
    assert result["knowledge_reply"] is None
    assert result["rag_sources"] is None
    assert result["chat_reply"] is None
    assert result["tools_reply"] is None
    assert result["final_reply"] is None
```

- [ ] **Step 6: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_begin_node.py -v`
Expected: FAIL —— 新增测试报 `KeyError: 'knowledge_reply'`，其余 8 条通过。

- [ ] **Step 7: begin_node 加重置并改用统一窗口**

`ai-python/app/graphs/hospital/nodes/begin.py`，import 区补一行：

```python
from app.graphs.hospital.memory import recent_messages, reset_turn_fields
```

函数体（第 188-211 行）改为：

```python
def begin_node(state: State) -> dict:
    """调用模型分类，并将通过 Pydantic 校验的结果写入图 State。"""

    messages = recent_messages(state)
    raw_decision = _classify(messages)
    decision = _parse_decision(raw_decision or "")

    # 首次输出无法通过 JSON/Pydantic 校验时，让模型按同一规则修正一次。
    if decision is None and raw_decision is not None:
        repaired_decision = _repair_invalid_json(messages, raw_decision)
        decision = _parse_decision(repaired_decision or "")
        if decision is None:
            logger.warning("Intent classifier returned invalid JSON after one repair attempt")

    selected_agents = _apply_department_tool_guard(
        _normalize_agents(decision),
        _latest_user_text(state),
    )
    logger.info(
        "intent_selected_agents conversation_id={} agents={}",
        state.get("conversation_id"),
        selected_agents,
    )
    # 本轮开头清零上一轮产出：checkpointer 会让这些字段跨轮存活。
    return {**reset_turn_fields(), "selected_agents": selected_agents}
```

- [ ] **Step 8: 其余三个节点改用统一窗口**

`ai-python/app/graphs/hospital/nodes/knowledge.py`：import 区补 `from app.graphs.hospital.memory import recent_messages`；第 111 行改为 `result = agent.invoke({"messages": recent_messages(state)})`；第 159 行 `*list(state.get("messages") or [])[-6:],` 改为 `*recent_messages(state),`。

`ai-python/app/graphs/hospital/nodes/chat.py`：import 区补同一行；第 47 行改为 `result = agent.invoke({"messages": recent_messages(state)})`。

`ai-python/app/graphs/hospital/nodes/tool.py`：import 区补同一行；`agent.invoke` 的第一个参数改为 `{"messages": recent_messages(state)}`。

- [ ] **Step 9: 确认再无裸切片**

Run: `python -m pytest -q && rg -n "\[-6:\]" app/`
Expected: pytest 全部 PASS；`rg` 无输出（退出码 1）。

- [ ] **Step 10: 提交**

```bash
git add ai-python/app/graphs/hospital/memory.py ai-python/app/graphs/hospital/nodes/ ai-python/tests/unit/test_memory.py ai-python/tests/unit/test_begin_node.py
git commit -m "fix(ai): 每轮开头重置节点产出，统一上下文窗口来源"
```

---

## Task 3: Redis Checkpointer 接入与 memoryEnabled 开关

**Files:**
- Create: `ai-python/app/graphs/hospital/checkpointing.py`
- Create: `ai-python/tests/unit/test_checkpointing.py`
- Create: `ai-python/tests/unit/test_turn_isolation.py`
- Modify: `ai-python/pyproject.toml:14-26`
- Modify: `ai-python/app/core/config.py:26-34`
- Modify: `ai-python/app/graphs/hospital/graphs.py`
- Modify: `ai-python/app/main.py:21-25`
- Modify: `ai-python/app/api/routes/chat.py`
- Modify: `ai-python/tests/test_app.py`
- Modify: `ai-python/.env.example`

**Interfaces:**
- Consumes: Task 2 的 `memory.reset_turn_fields`；Task 1 的 `HospitalToolContext` context schema。
- Produces: `graphs.build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph`；`graphs.graph`（无 checkpointer，供 `langgraph.json` 与 `memoryEnabled=false`）；`checkpointing.memory_lifespan()`（async context manager）；`checkpointing.get_memory_graph() -> CompiledStateGraph | None`；`checkpointing.set_memory_graph(graph) -> None`；`checkpointing.get_checkpointer() -> BaseCheckpointSaver | None`；`Settings.redis_url: str`；`Settings.checkpoint_ttl_minutes: int`。

- [ ] **Step 1: 装依赖并核实 Shallow saver 的 API**

```bash
cd ai-python
python -m pip install "langgraph-checkpoint-redis>=0.5.2,<0.6"
python -c "from langgraph.checkpoint.redis.aio import AsyncShallowRedisSaver as S; import inspect; print(inspect.signature(S.from_conn_string)); print(hasattr(S,'adelete_thread'), hasattr(S,'asetup'))"
```

Expected: 打印出的签名里含 `ttl` 参数，且两个 `hasattr` 都是 `True`。若 `from_conn_string` 不接受 `ttl`，改用 `AsyncShallowRedisSaver(redis_url=..., ttl=...)` 构造并手动 `await saver.asetup()`，其余步骤不变。

- [ ] **Step 2: 依赖写进 pyproject**

`ai-python/pyproject.toml` 的 `dependencies` 列表，在 `"langgraph",` 之后插入两行：

```toml
  "langgraph-checkpoint-redis>=0.5.2,<0.6",
  "redis>=5.2.1",
```

- [ ] **Step 3: 写图工厂与注册表的失败测试**

创建 `ai-python/tests/unit/test_checkpointing.py`：

```python
import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.hospital import checkpointing, graphs


def test_module_level_graph_has_no_checkpointer():
    """langgraph.json 导出的实例必须是无状态的，导入时不得连接 Redis。"""

    assert graphs.graph.checkpointer is None


def test_build_graph_accepts_a_checkpointer():
    saver = InMemorySaver()

    assert graphs.build_graph(checkpointer=saver).checkpointer is saver


def test_memory_graph_registry_defaults_to_empty():
    checkpointing.set_memory_graph(None)

    assert checkpointing.get_memory_graph() is None


def test_memory_graph_registry_round_trips():
    sentinel = object()
    try:
        checkpointing.set_memory_graph(sentinel)
        assert checkpointing.get_memory_graph() is sentinel
    finally:
        checkpointing.set_memory_graph(None)


async def test_memory_lifespan_is_a_noop_without_redis_url(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AI_REDIS_URL", "")
    get_settings.cache_clear()
    try:
        async with checkpointing.memory_lifespan() as saver:
            assert saver is None
            assert checkpointing.get_memory_graph() is None
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 4: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_checkpointing.py -v`
Expected: FAIL —— `AttributeError: module 'app.graphs.hospital.graphs' has no attribute 'build_graph'`

- [ ] **Step 5: 配置项加 Redis**

`ai-python/app/core/config.py`，在 `tavily_api_key` 之前插入：

```python
    redis_url: str = Field("", validation_alias="AI_REDIS_URL")
    checkpoint_ttl_minutes: int = Field(
        1440,
        validation_alias="AI_CHECKPOINT_TTL_MINUTES",
    )
```

- [ ] **Step 6: graphs.py 改成工厂**

`ai-python/app/graphs/hospital/graphs.py` 全文改为：

```python
from app.graphs.hospital.nodes.begin import begin_node
from app.graphs.hospital.nodes.chat import chat_node
from app.graphs.hospital.nodes.final import final_node
from app.graphs.hospital.nodes.knowledge import knowledge_node
from app.graphs.hospital.nodes.tool import tool_node
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.context import HospitalToolContext
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


def _workflow() -> StateGraph:
    workflow = StateGraph(State, context_schema=HospitalToolContext)

    workflow.add_node("begin_node", begin_node)
    workflow.add_node("knowledge_node", knowledge_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tool_node", tool_node)
    workflow.add_node("final_node", final_node)

    workflow.add_edge(START, "begin_node")
    workflow.add_edge("begin_node", "knowledge_node")
    workflow.add_edge("knowledge_node", "chat_node")
    workflow.add_edge("chat_node", "tool_node")
    workflow.add_edge("tool_node", "final_node")
    workflow.add_edge("final_node", END)

    return workflow


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """按需编译对话图。checkpointer 为 None 时得到无记忆实例。"""

    return _workflow().compile(checkpointer=checkpointer)


# langgraph.json 导出该实例，且 memoryEnabled=false 时也用它。
# 必须保持无 checkpointer：模块导入阶段不允许连接 Redis。
graph = build_graph()
```

- [ ] **Step 7: 创建 checkpointer 生命周期模块**

创建 `ai-python/app/graphs/hospital/checkpointing.py`：

```python
"""Redis checkpointer 的生命周期，以及带记忆图的进程内注册表。

Redis 连接只在应用启动时建立一次。选用 Shallow saver：每个 thread 只保留最新
一份 checkpoint。生产 Redis 内存很小且是 allkeys-lru，保留全部历史版本会被淘汰
淘汰到状态损坏，而本项目只需要「恢复到最新」，不需要时间旅行。
"""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, AsyncIterator

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.graphs import build_graph

_memory_graph: Any | None = None
_checkpointer: Any | None = None


def get_memory_graph() -> Any | None:
    """带 checkpointer 的图；未启用记忆时为 None。"""

    return _memory_graph


def set_memory_graph(graph: Any | None) -> None:
    global _memory_graph
    _memory_graph = graph


def get_checkpointer() -> Any | None:
    return _checkpointer


def _set_checkpointer(saver: Any | None) -> None:
    global _checkpointer
    _checkpointer = saver


@asynccontextmanager
async def memory_lifespan() -> AsyncIterator[Any | None]:
    """在应用生命周期内持有 Redis checkpointer。"""

    settings = get_settings()
    if not settings.redis_url:
        logger.warning("checkpointer_disabled reason=AI_REDIS_URL_not_configured")
        yield None
        return

    from langgraph.checkpoint.redis.aio import AsyncShallowRedisSaver

    ttl = {
        "default_ttl": settings.checkpoint_ttl_minutes,
        "refresh_on_read": True,
    }
    # 只有「建立连接」这一段允许降级。try 不能包住 yield，
    # 否则应用运行期抛出的异常会被这里吞掉并触发二次 yield。
    stack = AsyncExitStack()
    try:
        saver = await stack.enter_async_context(
            AsyncShallowRedisSaver.from_conn_string(settings.redis_url, ttl=ttl)
        )
        await saver.asetup()
    except Exception:
        # 记忆是增强能力，不能让 Redis 故障拖垮整个 AI 服务。
        logger.exception("checkpointer_setup_failed falling_back_to_stateless_graph")
        await stack.aclose()
        yield None
        return

    _set_checkpointer(saver)
    set_memory_graph(build_graph(checkpointer=saver))
    logger.info("checkpointer_ready ttl_minutes={}", settings.checkpoint_ttl_minutes)
    try:
        yield saver
    finally:
        set_memory_graph(None)
        _set_checkpointer(None)
        await stack.aclose()
```

- [ ] **Step 8: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_checkpointing.py -v`
Expected: PASS，共 5 条。

- [ ] **Step 9: main.py 挂上 lifespan**

`ai-python/app/main.py`，import 区补两行：

```python
from contextlib import asynccontextmanager
```

以及在 `from app.api.routes import chat, health` 之后：

```python
from app.graphs.hospital.checkpointing import memory_lifespan
```

在 `create_app` 之前加：

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    async with memory_lifespan():
        yield
```

`create_app` 里的 `FastAPI(...)` 构造改为：

```python
    app = FastAPI(title="WenRun AI API", version="0.1.0", lifespan=lifespan)
```

- [ ] **Step 10: 写路由选图与 thread_id 的失败测试**

在 `ai-python/tests/test_app.py` 末尾追加：

```python
def test_graph_config_uses_conversation_id_as_thread_id():
    from app.models.chat import ChatRequest

    request = ChatRequest(message="你好", conversationId="conv-42")

    assert chat_route._graph_config(request) == {
        "configurable": {"thread_id": "conv-42"}
    }


def test_chat_stream_prefers_memory_graph(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    from app.graphs.hospital import checkpointing

    captured: dict = {}

    class MemoryGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["config"] = config
            yield {"type": "values", "data": {"final_reply": "记忆图回复"}}

    class StatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["used_stateless"] = True
            yield {"type": "values", "data": {"final_reply": "无记忆回复"}}

    monkeypatch.setattr(chat_route, "graph", StatelessGraph())
    checkpointing.set_memory_graph(MemoryGraph())
    try:
        client = TestClient(create_app())
        response = client.post(
            "/v1/chat/stream",
            headers=headers,
            json={"message": "你好", "conversationId": "conv-42"},
        )
    finally:
        checkpointing.set_memory_graph(None)

    assert response.status_code == 200
    assert _sse_events(response)[-1]["reply"] == "记忆图回复"
    assert captured["config"] == {"configurable": {"thread_id": "conv-42"}}
    assert "used_stateless" not in captured


def test_chat_stream_falls_back_to_stateless_graph_when_memory_disabled(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    from app.graphs.hospital import checkpointing

    class MemoryGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            raise AssertionError("memoryEnabled=false 时不得使用记忆图")
            yield  # pragma: no cover

    class StatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            yield {"type": "values", "data": {"final_reply": "无记忆回复"}}

    monkeypatch.setattr(chat_route, "graph", StatelessGraph())
    checkpointing.set_memory_graph(MemoryGraph())
    try:
        client = TestClient(create_app())
        response = client.post(
            "/v1/chat/stream",
            headers=headers,
            json={
                "message": "你好",
                "conversationId": "conv-42",
                "memoryEnabled": False,
            },
        )
    finally:
        checkpointing.set_memory_graph(None)

    assert _sse_events(response)[-1]["reply"] == "无记忆回复"
```

同时把已有三个 FakeGraph 的 `astream` 签名再补上 `config`：

```python
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
```

- [ ] **Step 11: 运行测试确认失败**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL —— `AttributeError: module 'app.api.routes.chat' has no attribute '_graph_config'`

- [ ] **Step 12: 路由接通选图与 thread_id**

`ai-python/app/api/routes/chat.py`，import 区补一行：

```python
from app.graphs.hospital.checkpointing import get_memory_graph
```

在 `_runtime_context` 之后加两个函数：

```python
def _graph_for(memory_enabled: bool):
    """启用记忆且 checkpointer 就绪时用带记忆的图，否则回落到无状态图。"""

    if memory_enabled:
        memory_graph = get_memory_graph()
        if memory_graph is not None:
            return memory_graph
    return graph


def _graph_config(request: ChatRequest) -> dict[str, Any]:
    """conversationId 即 checkpointer 的 thread_id。归属由 Java 侧校验。"""

    return {"configurable": {"thread_id": request.conversation_id}}
```

`_stream_graph` 改为：

```python
async def _stream_graph(
    request: ChatRequest, delegation: DelegationContext
) -> AsyncIterator[dict[str, Any]]:
    """生成 LangGraph v2 流式片段。"""

    async for part in _graph_for(request.memory_enabled).astream(
        _initial_state(request),
        context=_runtime_context(delegation),
        config=_graph_config(request),
        stream_mode=["messages", "values"],
        subgraphs=True,
        version="v2",
    ):
        if isinstance(part, dict):
            yield part
```

- [ ] **Step 13: 运行测试确认通过**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS，全部通过。

- [ ] **Step 14: 写串轮回归测试（本计划最关键的测试）**

创建 `ai-python/tests/unit/test_turn_isolation.py`：

```python
import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

import json

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.hospital import graphs
from app.graphs.hospital.nodes import begin as begin_module
from app.graphs.hospital.nodes import chat as chat_module
from app.graphs.hospital.nodes import final as final_module
from app.graphs.hospital.nodes import knowledge as knowledge_module
from app.graphs.hospital.tools.context import HospitalToolContext

CONTEXT = HospitalToolContext("delegated-token", "trace-1")
CONFIG = {"configurable": {"thread_id": "isolation-thread"}}


class _StubRetriever:
    def invoke(self, query):
        return [Document(page_content="多休息多喝水", metadata={"source_name": "院内资料", "page": 1})]


class _StubAgent:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def invoke(self, payload, **kwargs):
        self.calls += 1
        return {"messages": [AIMessage(content=self.reply)]}


def _stub_nodes(monkeypatch, intents):
    """按回合顺序返回意图，并把所有 LLM 出口替换成确定性桩。"""

    pending = iter(intents)
    monkeypatch.setattr(
        begin_module,
        "_classify",
        lambda messages: json.dumps({"selected_agents": next(pending)}),
    )
    monkeypatch.setattr(knowledge_module, "get_hospital_retriever", lambda: _StubRetriever())
    monkeypatch.setattr(
        knowledge_module,
        "model",
        type("M", (), {"invoke": staticmethod(lambda messages: AIMessage(content="感冒建议：多喝水"))})(),
    )
    chat_agent = _StubAgent("不客气，还有需要随时说。")
    monkeypatch.setattr(chat_module, "agent", chat_agent)
    final_agent = _StubAgent("这不该被调用")
    monkeypatch.setattr(final_module, "final_agent", final_agent)
    return chat_agent, final_agent


def test_second_turn_does_not_reuse_previous_turn_replies(monkeypatch):
    _, final_agent = _stub_nodes(monkeypatch, [["knowledge"], ["chat"]])
    graph = graphs.build_graph(checkpointer=InMemorySaver())

    first = graph.invoke(
        {"messages": [HumanMessage(content="感冒吃什么药")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )
    assert first["final_reply"] == "感冒建议：多喝水"

    second = graph.invoke(
        {"messages": [HumanMessage(content="谢谢你啊")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )

    # 上一轮的知识回复必须已被清零，否则 final_node 会把两条一起汇总。
    assert second["knowledge_reply"] is None
    assert second["rag_sources"] is None
    assert second["final_reply"] == "不客气，还有需要随时说。"
    assert final_agent.calls == 0


def test_checkpointer_accumulates_history_across_turns(monkeypatch):
    _stub_nodes(monkeypatch, [["chat"], ["chat"]])
    graph = graphs.build_graph(checkpointer=InMemorySaver())

    graph.invoke(
        {"messages": [HumanMessage(content="你好")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )
    second = graph.invoke(
        {"messages": [HumanMessage(content="谢谢")], "conversation_id": "isolation-thread"},
        context=CONTEXT,
        config=CONFIG,
    )

    contents = [message.content for message in second["messages"]]
    assert contents == ["你好", "不客气，还有需要随时说。", "谢谢", "不客气，还有需要随时说。"]
```

- [ ] **Step 15: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_turn_isolation.py -v`
Expected: PASS，共 2 条。若 `test_second_turn_does_not_reuse_previous_turn_replies` 失败，说明 Task 2 的重置未生效，回去修 `begin_node`。

- [ ] **Step 16: 补 Python 侧环境变量样例**

`ai-python/.env.example` 末尾追加：

```dotenv
# 会话记忆（LangGraph checkpointer）。留空则关闭记忆，图退化为单轮无状态。
# 必须是 Redis 8+（自带 RedisJSON 与 RediSearch）；db 与 Java 登录 Session 分开。
AI_REDIS_URL=redis://localhost:6379/1
# checkpoint 存活时长（分钟），读到即续期
AI_CHECKPOINT_TTL_MINUTES=1440
```

- [ ] **Step 17: 全量测试并提交**

```bash
python -m pytest -q
git add ai-python/pyproject.toml ai-python/.env.example ai-python/app ai-python/tests
git commit -m "feat(ai): 接入 Redis checkpointer，conversationId 作为 thread_id"
```

Expected: pytest 全部 PASS。

---

## Task 4: 记忆清理接口与 Java 级联删除

`aiController.deleteConversation` 目前只删 MySQL 消息，Redis 里的 checkpoint 会残留到 TTL 过期——用户「删除会话」后重开同名会话仍能被旧记忆污染。

**Files:**
- Modify: `ai-python/app/api/routes/chat.py`
- Modify: `ai-python/tests/test_app.py`
- Modify: `backend-java/src/main/java/com/wenrun/ai/service/aiService.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java:100-106`

**Interfaces:**
- Consumes: Task 3 的 `checkpointing.get_checkpointer()`。
- Produces: `DELETE /v1/chat/memory/{conversation_id}` → 204（需 `X-Api-Key`，不需委托令牌）；`aiService.deleteConversationMemory(String conversationId)`（best-effort，不抛异常）。

- [ ] **Step 1: 写失败测试**

在 `ai-python/tests/test_app.py` 末尾追加：

```python
def test_delete_conversation_memory_purges_thread(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()
    from app.graphs.hospital import checkpointing

    deleted: list[str] = []

    class FakeCheckpointer:
        async def adelete_thread(self, thread_id):
            deleted.append(thread_id)

    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: FakeCheckpointer())
    client = TestClient(create_app())
    response = client.delete(
        "/v1/chat/memory/conv-42", headers={"X-Api-Key": "test-key"}
    )

    assert response.status_code == 204
    assert deleted == ["conv-42"]


def test_delete_conversation_memory_succeeds_when_memory_disabled(monkeypatch):
    monkeypatch.setenv("AI_INTERNAL_API_KEY", "test-key")
    get_settings.cache_clear()

    monkeypatch.setattr(chat_route, "get_checkpointer", lambda: None)
    client = TestClient(create_app())
    response = client.delete(
        "/v1/chat/memory/conv-42", headers={"X-Api-Key": "test-key"}
    )

    assert response.status_code == 204
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_app.py -k delete_conversation_memory -v`
Expected: FAIL —— 405 Method Not Allowed

- [ ] **Step 3: 实现 Python 清理接口**

`ai-python/app/api/routes/chat.py`：把 Task 3 加的 import 改为

```python
from app.graphs.hospital.checkpointing import get_checkpointer, get_memory_graph
```

在 import 区补 `from starlette.responses import Response, StreamingResponse`（替换原来只导入 `StreamingResponse` 的那行），并在 `upload_knowledge_document` 之后加：

```python
@router.delete("/memory/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_memory(conversation_id: str) -> Response:
    """清除单个会话的 checkpoint。会话归属由 Java 侧校验后才会调用。"""

    checkpointer = get_checkpointer()
    if checkpointer is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        await checkpointer.adelete_thread(conversation_id)
    except Exception:
        logger.exception(
            "conversation_memory_delete_failed conversation_id={}", conversation_id
        )
        raise HTTPException(status_code=500, detail="会话记忆清理失败") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS，全部通过。

- [ ] **Step 5: Java 侧加清理调用**

`backend-java/src/main/java/com/wenrun/ai/service/aiService.java`：类上加 `@Slf4j`，import 区补 `import lombok.extern.slf4j.Slf4j;`。在 `streamChat` 之后加：

```java
    /** 删除会话时清理 Python 侧的 checkpoint。记忆清理失败不应阻塞用户删除操作。 */
    public void deleteConversationMemory(String conversationId) {
        if (!StringUtils.hasText(conversationId)) {
            return;
        }
        try {
            pythonClient.delete()
                    .uri("/v1/chat/memory/{conversationId}", conversationId)
                    .headers(headers -> {
                        if (StringUtils.hasText(apiKey)) {
                            headers.set("X-Api-Key", apiKey);
                        }
                        String requestId = RequestTrace.get();
                        if (RequestTrace.isUsable(requestId)) {
                            headers.set(RequestTrace.HEADER_NAME, requestId);
                        }
                    })
                    .retrieve()
                    .toBodilessEntity();
        } catch (Exception ex) {
            log.warn("清理会话记忆失败 conversationId={}: {}", conversationId, ex.getMessage());
        }
    }
```

- [ ] **Step 6: 控制器级联调用**

`backend-java/.../ai/controller/aiController.java` 第 100-106 行改为：

```java
    @DeleteMapping("/conversations/{conversationId}")
    public Result<Void> deleteConversation(@PathVariable String conversationId) {
        Long userId = UserContext.getUserId();
        ownershipService.assertOwned(conversationId, userId);
        chatMessageRepository.deleteByConversationId(conversationId);
        aiService.deleteConversationMemory(conversationId);
        return Result.success();
    }
```

- [ ] **Step 7: 跑 Java 测试**

Run: `cd backend-java && mvn -q test`
Expected: BUILD SUCCESS。若本机没有 Maven，按 TODO.md P0-3 先补 Maven Wrapper，或在有 Maven 的环境执行；不要跳过。

- [ ] **Step 8: 提交**

```bash
git add ai-python/app/api/routes/chat.py ai-python/tests/test_app.py backend-java/src/main/java/com/wenrun/ai/
git commit -m "feat: 删除会话时级联清理 Agent 会话记忆"
```

---

## Task 5: 历史摘要压缩

长会话下 checkpoint 与 prompt 会无限膨胀。摘要节点放在 `final_node` 之后：此时 token 已经流给前端，只有 `done` 事件被延迟，比放在图开头拖慢首字体验好得多。压缩时用 `RemoveMessage` 真正裁掉旧消息，把 checkpoint 体积压住。

**Files:**
- Modify: `ai-python/app/graphs/hospital/state.py`
- Modify: `ai-python/app/graphs/hospital/memory.py`
- Create: `ai-python/app/graphs/hospital/nodes/summarize.py`
- Modify: `ai-python/app/graphs/hospital/graphs.py`
- Modify: `ai-python/tests/unit/test_memory.py`
- Create: `ai-python/tests/unit/test_summarize_node.py`

**Interfaces:**
- Consumes: Task 2 的 `memory.recent_messages`；Task 3 的 `graphs._workflow`。
- Produces: `State.summary: str | None`；`memory.SUMMARY_TRIGGER_MESSAGES: int = 12`；`memory.SUMMARY_KEEP_MESSAGES: int = 6`；`memory.needs_summary(state: State) -> bool`；`memory.split_for_summary(state: State) -> tuple[list[BaseMessage], list[BaseMessage]]`；`summarize.summarize_node(state: State) -> dict`。`recent_messages` 签名不变，但返回值前会拼一条摘要 SystemMessage。

- [ ] **Step 1: 写失败测试**

在 `ai-python/tests/unit/test_memory.py` 末尾追加：

```python
def test_recent_messages_prepends_running_summary():
    history = [HumanMessage(content="q"), AIMessage(content="a")]

    result = memory.recent_messages({"messages": history, "summary": "患者此前咨询过感冒用药"})

    assert result[0].type == "system"
    assert "患者此前咨询过感冒用药" in result[0].content
    assert result[1:] == history


def test_recent_messages_ignores_blank_summary():
    history = [HumanMessage(content="q")]

    assert memory.recent_messages({"messages": history, "summary": "   "}) == history


def test_needs_summary_triggers_only_above_threshold():
    short = [HumanMessage(content=str(index)) for index in range(12)]
    long = [HumanMessage(content=str(index)) for index in range(13)]

    assert memory.needs_summary({"messages": short}) is False
    assert memory.needs_summary({"messages": long}) is True


def test_split_for_summary_keeps_recent_tail():
    history = [HumanMessage(content=str(index)) for index in range(14)]

    dropped, kept = memory.split_for_summary({"messages": history})

    assert dropped == history[:-6]
    assert kept == history[-6:]
```

创建 `ai-python/tests/unit/test_summarize_node.py`：

```python
import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from app.graphs.hospital.nodes import summarize as summarize_module


def _history(count: int) -> list:
    messages = []
    for index in range(count):
        messages.append(HumanMessage(content=f"问题{index}", id=f"h{index}"))
        messages.append(AIMessage(content=f"回答{index}", id=f"a{index}"))
    return messages


def test_summarize_node_skips_short_conversations():
    assert summarize_module.summarize_node({"messages": _history(3)}) == {}


def test_summarize_node_compresses_and_removes_old_messages(monkeypatch):
    captured: dict = {}

    class FakeModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return AIMessage(content="患者先后咨询了感冒用药与内科号源。")

    monkeypatch.setattr(summarize_module, "model", FakeModel())

    history = _history(7)  # 14 条，超过阈值 12
    result = summarize_module.summarize_node({"messages": history})

    assert result["summary"] == "患者先后咨询了感冒用药与内科号源。"
    removed = result["messages"]
    assert all(isinstance(item, RemoveMessage) for item in removed)
    assert [item.id for item in removed] == [message.id for message in history[:-6]]
    assert "问题0" in captured["messages"][-1].content


def test_summarize_node_carries_existing_summary_into_prompt(monkeypatch):
    captured: dict = {}

    class FakeModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return AIMessage(content="更新后的摘要")

    monkeypatch.setattr(summarize_module, "model", FakeModel())

    result = summarize_module.summarize_node(
        {"messages": _history(7), "summary": "已有摘要"}
    )

    assert result["summary"] == "更新后的摘要"
    assert "已有摘要" in captured["messages"][-1].content


def test_summarize_node_keeps_turn_alive_when_model_fails(monkeypatch):
    class BrokenModel:
        def invoke(self, messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(summarize_module, "model", BrokenModel())

    assert summarize_module.summarize_node({"messages": _history(7)}) == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_memory.py tests/unit/test_summarize_node.py -v`
Expected: FAIL —— `AttributeError: module 'app.graphs.hospital.memory' has no attribute 'needs_summary'` 与 `ModuleNotFoundError: ...nodes.summarize`

- [ ] **Step 3: State 加 summary 字段**

`ai-python/app/graphs/hospital/state.py`，在 `final_reply` 之后加一行：

```python
    summary: str | None  # 摘要节点写入的历史压缩结果，跨轮存活
```

`summary` 不进 `TURN_SCOPED_REPLY_FIELDS`——它是跨轮记忆，不能每轮清零。

- [ ] **Step 4: memory 模块加摘要策略**

`ai-python/app/graphs/hospital/memory.py`：import 区改为

```python
from langchain_core.messages import BaseMessage, SystemMessage
```

在 `TURN_SCOPED_REPLY_FIELDS` 之后加两个常量：

```python
# 超过该条数才触发压缩。12 条约等于 6 轮问答，避免短会话白花一次 LLM 调用。
SUMMARY_TRIGGER_MESSAGES = 12
# 压缩后原样保留的尾部条数，与 RECENT_MESSAGE_WINDOW 对齐，保证窗口内不出现空洞。
SUMMARY_KEEP_MESSAGES = RECENT_MESSAGE_WINDOW
```

`recent_messages` 改为：

```python
def recent_messages(
    state: State, limit: int = RECENT_MESSAGE_WINDOW
) -> list[BaseMessage]:
    """所有节点唯一的上下文窗口来源；有历史摘要时拼在最前面。"""

    tail = list(state.get("messages") or [])[-limit:]
    summary = state.get("summary")
    if isinstance(summary, str) and summary.strip():
        return [SystemMessage(content=f"【历史摘要】\n{summary.strip()}"), *tail]
    return tail
```

文件末尾追加：

```python
def needs_summary(state: State) -> bool:
    """消息条数超过阈值才压缩。"""

    return len(state.get("messages") or []) > SUMMARY_TRIGGER_MESSAGES


def split_for_summary(state: State) -> tuple[list[BaseMessage], list[BaseMessage]]:
    """切成「待压缩的旧消息」与「原样保留的尾部消息」。"""

    messages = list(state.get("messages") or [])
    return messages[:-SUMMARY_KEEP_MESSAGES], messages[-SUMMARY_KEEP_MESSAGES:]
```

- [ ] **Step 5: 创建摘要节点**

创建 `ai-python/app/graphs/hospital/nodes/summarize.py`：

```python
"""历史摘要节点：在 final_node 之后压缩旧消息，控制 prompt 与 checkpoint 体积。

放在图末尾而不是开头，是因为此时回复已经流给前端，只有 done 事件被延迟，
不会拖慢首 Token。压缩用 RemoveMessage 真正裁掉旧消息，否则 checkpoint 会无限增长。
"""

from app.graphs.hospital.memory import needs_summary, split_for_summary
from app.graphs.hospital.state import State
from app.models.chat import model
from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from loguru import logger

SUMMARY_SYSTEM_PROMPT = """你是温润诊所患者端对话的历史压缩器，不对患者说话。
把给定的历史对话压缩成一段中文摘要，供后续轮次当作背景使用。

必须保留：
- 患者自述的症状、持续时间、用药情况、过敏史（标明是「患者自述」，不是诊断结论）
- 患者关心的科室、医生、日期、时间段
- 已经查到的号源、排班、预约等事实结果
- 尚未办完的事情和患者明确表达的偏好

必须遵守：
- 只压缩已有内容，不补充医学知识，不新增诊断、药名、剂量
- 不复述完整对话，不写「本次对话中」这类开场白
- 不输出 Markdown 标题或列表符号，用连贯短句
- 控制在 300 字以内
- 直接输出摘要正文，不要任何解释
"""


def _build_prompt(existing_summary: str | None, transcript: str) -> list:
    sections = []
    if isinstance(existing_summary, str) and existing_summary.strip():
        sections.append(f"【已有摘要】\n{existing_summary.strip()}")
    sections.append(f"【需要并入摘要的历史对话】\n{transcript}")
    return [
        SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(sections)),
    ]


def _transcript(messages: list) -> str:
    lines = []
    for message in messages:
        speaker = "患者" if getattr(message, "type", "") == "human" else "助手"
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            lines.append(f"{speaker}：{content.strip()}")
    return "\n".join(lines)


def summarize_node(state: State) -> dict:
    if not needs_summary(state):
        return {}

    dropped, kept = split_for_summary(state)
    transcript = _transcript(dropped)
    if not transcript:
        return {}

    try:
        response = model.invoke(_build_prompt(state.get("summary"), transcript))
    except Exception:
        # 压缩失败不能影响本轮回复，下一轮会再次触发。
        logger.exception(
            "conversation_summary_failed conversation_id={}", state.get("conversation_id")
        )
        return {}

    content = getattr(response, "content", "")
    summary = content.strip() if isinstance(content, str) else ""
    if not summary:
        return {}

    logger.info(
        "conversation_summarized conversation_id={} dropped={} tokens_before={} tokens_after={}",
        state.get("conversation_id"),
        len(dropped),
        count_tokens_approximately(dropped + kept),
        count_tokens_approximately([SystemMessage(content=summary), *kept]),
    )
    return {
        "summary": summary,
        "messages": [
            RemoveMessage(id=message.id) for message in dropped if getattr(message, "id", None)
        ],
    }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_memory.py tests/unit/test_summarize_node.py -v`
Expected: PASS，共 12 条。

- [ ] **Step 7: 摘要节点接入图**

`ai-python/app/graphs/hospital/graphs.py`：import 区补 `from app.graphs.hospital.nodes.summarize import summarize_node`；`_workflow()` 里 `add_node("final_node", final_node)` 之后加一行 `workflow.add_node("summarize_node", summarize_node)`；把 `workflow.add_edge("final_node", END)` 换成两行：

```python
    workflow.add_edge("final_node", "summarize_node")
    workflow.add_edge("summarize_node", END)
```

摘要节点不需要出现在 `chat.py::_stream_visible_nodes` 里——它不在可见集合中，其模型输出会被 `_is_visible_message_node` 自动过滤。

- [ ] **Step 8: 补一条端到端压缩测试**

在 `ai-python/tests/unit/test_turn_isolation.py` 末尾追加：

```python
def test_long_conversation_gets_compressed_into_summary(monkeypatch):
    _stub_nodes(monkeypatch, [["chat"]] * 8)
    monkeypatch.setattr(
        "app.graphs.hospital.nodes.summarize.model",
        type("M", (), {"invoke": staticmethod(lambda messages: AIMessage(content="患者多次寒暄致谢。"))})(),
    )
    graph = graphs.build_graph(checkpointer=InMemorySaver())

    state = {}
    for index in range(8):
        state = graph.invoke(
            {
                "messages": [HumanMessage(content=f"你好{index}")],
                "conversation_id": "isolation-thread",
            },
            context=CONTEXT,
            config=CONFIG,
        )

    assert state["summary"] == "患者多次寒暄致谢。"
    # 压缩后消息数被压回窗口附近，不再随轮次线性增长。
    assert len(state["messages"]) <= 8
```

- [ ] **Step 9: 全量测试并提交**

```bash
python -m pytest -q
git add ai-python/app ai-python/tests
git commit -m "feat(ai): 长会话历史自动摘要并裁剪 checkpoint"
```

Expected: pytest 全部 PASS。

---

## Task 6: 基础设施与文档对齐

**Files:**
- Modify: `docker-compose.prod.yml:1-26,57-78,99-127`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `docs/AI模块开发与运维指南.md:196-200`
- Modify: `docs/求职项目评估与流程图.md:25-28,44-49`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: Task 3 的 `AI_REDIS_URL`、`AI_CHECKPOINT_TTL_MINUTES`。
- Produces: 无代码接口。

- [ ] **Step 1: 生产 Redis 升到 8 并调整内存预算**

`docker-compose.prod.yml` 的 `redis` 服务改为：

```yaml
  redis:
    image: redis:8-alpine
    container_name: wenrun-redis
    restart: unless-stopped
    mem_limit: 192m
    memswap_limit: 192m
    cpus: 0.15
    logging: *default-logging
    # Redis 8 内置 RedisJSON 与 Query Engine，langgraph-checkpoint-redis 需要它们。
    # Session 在 db0，Agent checkpoint 在 db1，避免 LRU 淘汰时互相踩。
    command: >
      redis-server
      --maxmemory 128mb
      --maxmemory-policy allkeys-lru
      --save ""
      --appendonly no
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    networks:
      - wenrun-net
```

同时把文件第 2 行的内存注释与第 14 行的镜像清单更新：`redis:7-alpine` 改成 `redis:8-alpine`，容器内存上限合计从「约 1.21GB（含 Redis 64m）」改为「约 1.34GB（含 Redis 192m）」。

- [ ] **Step 2: Python 服务连上 Redis**

`docker-compose.prod.yml` 的 `ai-python` 服务：`depends_on` 补 redis，`environment` 里 `QDRANT_MEMORY_COLLECTION` 之后加两行：

```yaml
    depends_on:
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
```

```yaml
      AI_REDIS_URL: ${AI_REDIS_URL:-redis://redis:6379/1}
      AI_CHECKPOINT_TTL_MINUTES: ${AI_CHECKPOINT_TTL_MINUTES:-1440}
```

`backend-java` 服务的 `environment` 里 `SPRING_DATA_REDIS_PORT` 之后加一行，把 Session 显式钉在 db0：

```yaml
      SPRING_DATA_REDIS_DATABASE: "0"
```

- [ ] **Step 3: 开发 Compose 加 Redis**

`docker-compose.yml` 用的是默认网络，没有 `networks:` 段，新服务也不要加。在 `mysql` 服务之后插入：

```yaml
  redis:
    image: redis:8-alpine
    ports:
      - "6379:6379"
    command: redis-server --save "" --appendonly no
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
```

`backend-java` 服务第 30 行的 `SPRING_DATA_REDIS_HOST` 默认值从 `host.docker.internal` 改为 `redis`（这条同时消掉 TODO.md P0-3 里「改掉 host.docker.internal」那一项），并在其 `depends_on` 里补：

```yaml
      redis:
        condition: service_healthy
```

`ai-python` 服务的 `environment` 里 `JAVA_TOOL_BASE_URL` 之后加两行，并补 `depends_on`：

```yaml
      AI_REDIS_URL: ${AI_REDIS_URL:-redis://redis:6379/1}
      AI_CHECKPOINT_TTL_MINUTES: ${AI_CHECKPOINT_TTL_MINUTES:-1440}
    depends_on:
      redis:
        condition: service_healthy
```

Qdrant 服务的补齐属于 TODO.md P0-3，不在本计划范围。

- [ ] **Step 4: 根目录环境变量样例**

`.env.example` 的 Redis 段落之后追加：

```dotenv
# Agent 会话记忆（LangGraph checkpointer）。必须 Redis 8+，db 与登录 Session 分开。
AI_REDIS_URL=redis://redis:6379/1
AI_CHECKPOINT_TTL_MINUTES=1440
```

- [ ] **Step 5: 更正 AI 模块文档**

`docs/AI模块开发与运维指南.md` 第 198 行那条「`memoryEnabled` 目前不产生实际记忆效果」改为：

```markdown
- `memoryEnabled` 已生效。为 `true` 且 `AI_REDIS_URL` 配置可用时，图使用 Redis checkpointer，`conversationId` 作为 `thread_id`，同一会话跨轮共享消息历史与摘要；为 `false` 或 checkpointer 不可用时，退化为单轮无状态图。历史超过 12 条消息后由 `summarize_node` 压缩为摘要，并用 `RemoveMessage` 裁剪旧消息。
- 委托令牌不进入 State，只通过 Runtime Context（`HospitalToolContext`）传递，不会写入 checkpoint。
- 删除会话时，Java 会调用 `DELETE /v1/chat/memory/{conversationId}` 级联清理 checkpoint。
```

- [ ] **Step 6: 更正求职评估文档**

`docs/求职项目评估与流程图.md` 第 27 行保留（现在为真），但第 26 行「挂号采用人工确认 interrupt」仍是未实现，按 TODO.md P0-1 的要求删除或改写为「挂号写操作尚未开放，Tool 仅只读」。第 44-49 行的 State / Config / Runtime Context 描述与实现一致，无需改动。第 164、171 行流程图里的 `LoadMemory` / `SaveMemory` 改为与实现对应的名字：`LoadMemory` 改为 `Checkpoint 恢复`，`SaveMemory` 改为 `摘要压缩`，第 177 行的 `SQLite Checkpoint` 改为 `Redis Checkpoint（Shallow + TTL）`。

- [ ] **Step 7: 更新 TODO**

`TODO.md` 的 P0-1 里两条勾掉并改写：「删除或改写 LangGraph checkpoint / 会话记忆和恢复」改为已实现说明；P2 的第一条「LangGraph 接入 checkpointer，`conversationId` 作为 `thread_id`」标记为已完成，并注明 HITL interrupt 的前置条件已就绪。

- [ ] **Step 8: 一条命令验收开发环境**

```bash
docker compose up --build -d redis
cd ai-python && AI_REDIS_URL=redis://localhost:6379/1 python -m uvicorn app.main:app --port 8000
```

Expected: 启动日志出现 `checkpointer_ready ttl_minutes=1440`。若出现 `checkpointer_setup_failed`，先确认 Redis 版本为 8+：

```bash
docker compose exec redis redis-cli INFO server | rg redis_version
docker compose exec redis redis-cli MODULE LIST
```

Expected: `redis_version:8.x`；`MODULE LIST` 能看到 `search` 与 `ReJSON`。

- [ ] **Step 9: 手工验收多轮记忆**

用 `curl` 连发两轮同一 `conversationId`，第二轮只说「内科」，确认回复承接第一轮的挂号意图而不是把「内科」当成孤立提问。

```bash
curl -N -X POST http://localhost:8000/v1/chat/stream \
  -H "X-Api-Key: $AI_INTERNAL_API_KEY" \
  -H "X-Delegated-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"我想挂号","conversationId":"manual-check"}'
```

Expected: 第二轮（把 `message` 换成 `内科`，`conversationId` 不变）的回复围绕挂号内科展开。

- [ ] **Step 10: 提交**

```bash
git add docker-compose.prod.yml docker-compose.yml .env.example docs/ TODO.md
git commit -m "chore: Redis 8 + 会话记忆基础设施，文档与实现对齐"
```

---

## 已知限制（要写进 README，面试时主动讲，不要等人问）

- **同一会话并发写 checkpoint 未加锁。** Java 侧 `clientRequestId` 幂等只能拦住重复提交的同一条消息；同一 `conversationId` 并发发送两条**不同**消息时，两次 `graph.astream` 会各自基于同一份 checkpoint 写回，后写的覆盖先写的，丢一轮历史。前端是单输入框串行发送，实际触发概率低。彻底解决要在 Java 侧按 `conversationId` 加 Redis 分布式锁或串行队列，属于后续工作。
- **记忆只是「患者自述」，不是病历。** 摘要 prompt 已要求标注自述来源、禁止新增诊断与药名，但模型仍可能把旧症状当成当前事实。任何医疗结论仍必须走 RAG 引用或 Tool 返回的真实数据，记忆不构成依据。
- **checkpoint 有 TTL 且可被 LRU 淘汰。** 生产 Redis 是 `allkeys-lru` + 128mb，默认 TTL 24 小时。超期或内存压力下记忆会消失，此时会话退化为单轮，不报错。MySQL `chat_messages` 仍保留完整消息，前端历史展示不受影响。
- **摘要会让最后一个 token 到 `done` 事件之间多一次 LLM 调用。** 只在消息超过 12 条时触发（约每 6 轮一次）。若实测延迟不可接受，可把 `summarize_node` 改为后台任务，但那需要额外的写冲突处理。

## 验收清单

- [ ] `rg -n "delegated_token" ai-python/app/graphs/hospital/state.py` 无输出
- [ ] `python -m pytest -q` 在 `ai-python` 下全绿
- [ ] `tests/unit/test_turn_isolation.py` 两条串轮回归测试通过
- [ ] `graphs.graph.checkpointer is None`（`langgraph.json` 与 `memoryEnabled=false` 仍可用）
- [ ] 生产 Compose 里 Redis 为 8+，Session 在 db0、checkpoint 在 db1
- [ ] 删除会话后重开同名 `conversationId`，不再出现旧记忆
- [ ] 文档中关于记忆的每句话都能在源码里指到实现
