# 多意图分流（起始节点 + 三 Agent）评估 TODO

日期：2026-08-20  
状态：待你评估，未开始写代码  
范围：仅 Python LangGraph 的意图识别、状态字段、节点跳转。  
明确不做：具体 RAG / Java Tool 实现、SSE 协议、前端改动。

---

## 0. 先请你拍板的结论

你的目标可以收敛成一句话：

> 患者一句话里可能同时要「挂号/查号」和「知识问答」甚至更多。起始节点用结构化输出做**多选意图**，把需要的 Agent 写进 `State`；后面每个业务节点只看自己的标记，有则执行、无则跳过。

下面默认按这个目标设计。请你先扫 **第 1 节待确认项**，再决定要不要按推荐方案落地。

---

## 1. 待你确认（评估重点）

请直接在这项上打勾或改字：

- [x] **意图取值目前为固定为三个**：`knowledge`（专业知识问答）、`chat`（普通聊天）、`tools`（工具调用，含挂号等）不过将来可能会添加更多但是不一定走同一条工作流
- [x] **多选**：一条用户消息可以同时命中 2～3 个 Agent
- [x] **空意图兜底**：三个都没命中时，强制走 `chat`，不要停在起始节点干等
- [x] **执行顺序（推荐）**：`knowledge` → `chat` → `tools`  
  原因：`tools` 里挂号会 `interrupt`。若先挂号再问答，确认弹窗会把知识问答拖到下一轮。非中断节点先跑完，最后再进工具。
- [x] **多 Agent 都跑完后要有一个汇总节点（这边需要额外添加一个agent主要用于汇总并精简）**：把各节点产出拼成一条对患者的回复（先规则拼接，不先再调一次大模型）
- [x] **起始节点用结构化输出**，但接受「不是 100%」：解析失败则重试 1 次，仍失败则兜底 `["chat"]`

若以上有任何一条不同意，先改这一节，再写代码。

---



## 2. 和现状的差距

当前 `State.intent` 是 `str | None`，只能单选，撑不住「既要挂号又要问诊」。

```13:15:ai-python/app/graphs/hospital/state.py
    conversation_id: str #会话id
    patient_id: int | None #患者id
    intent: str | None #用户意图
```

起始节点 `begin.py` 已有意图 Agent，但还没有：

- 结构化输出 schema
- 把结果写回 `State`
- 图、条件边、三个业务节点

---



## 3. 推荐方案：线性流水线 + 节点内跳过

这和你说的「每个节点看看 state 上有没有被起始节点标记」最贴。

```mermaid
flowchart LR
    START --> begin
    begin --> knowledge
    knowledge --> chat
    chat --> tools
    tools --> merge
    merge --> END
```



每个业务节点内部：

```text
if 自己的标记不在 state.selected_agents 里:
    return {}          # 什么都不做，图继续往下
else:
    执行本 Agent
    把本段回复写进 state
```


| 优点                      | 缺点                                     |
| ----------------------- | -------------------------------------- |
| 和你的心智模型一致，图简单           | 即使用户只闲聊，也会「路过」knowledge/tools（但跳过成本极低） |
| 挂号 interrupt 仍是一条线，好恢复  | 不能并行，总延迟是各 Agent 相加                    |
| 不需要 `Send` / map-reduce | 三个节点都要记得写跳过逻辑                          |


**不推荐本轮做的两种替代：**

1. **条件边只通往被选中的节点**
  多选时边的组合有 7 种，图会很快变乱。
2. `Send` **并行扇出**
  知识问答和闲聊可以并行，但和挂号 interrupt 混在一起不好做；留给以后。

---



## 4. State 建议（替换现在的单字符串 intent）

```python
from typing import Literal
from langgraph.graph import MessagesState

AgentName = Literal["knowledge", "chat", "tools"]


class State(MessagesState):
    conversation_id: str
    patient_id: int | None
    selected_agents: list[AgentName]   # 起始节点写入，可多选
    knowledge_reply: str | None        # 知识节点写入
    chat_reply: str | None             # 闲聊节点写入
    tools_reply: str | None            # 工具节点写入
    final_reply: str | None            # 汇总节点写入
```

评估点：

- [ ] 用 `selected_agents: list[...]` 而不是三个 bool。列表能表达「选了谁」，以后若要顺序也可复用。
- [ ] 各节点回复分字段存放，避免大家抢同一个 `messages` 把过程话术暴露给患者。
- [ ] `messages` 仍只保存患者原话 + 最终对患者可见的助手回复（由汇总节点追加）。

---



## 5. 起始节点：结构化输出（不是 100%）

LangChain 的做法是给 `create_agent(..., response_format=Schema)`，结果在 `result["structured_response"]`。  
文档：[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)

建议 schema：

```python
from typing import Literal
from pydantic import BaseModel, Field

AgentName = Literal["knowledge", "chat", "tools"]


class IntentDecision(BaseModel):
    """根据患者最新一句话，判断需要启动哪些内部 Agent。可多选。"""

    selected_agents: list[AgentName] = Field(
        min_length=1,
        description=(
            "可多选。"
            "knowledge=疾病/科室/就诊须知等专业知识；"
            "chat=寒暄、闲聊、感谢、与就诊无关的对话；"
            "tools=挂号、查医生、查排班、查号源等需要调医院接口的操作。"
        ),
    )
    reason: str = Field(description="一两句中文，说明为什么这样选。仅内部日志用。")
```

起始节点伪流程：

1. 只把**最新一条用户消息**（可带很短的窗口上下文）交给意图 Agent。
2. `create_agent(model, tools=[], response_format=IntentDecision, system_prompt=...)`
3. 读取 `structured_response.selected_agents`，去重后写入 `state.selected_agents`。
4. 若 `structured_response` 为空：再 invoke 一次；仍空则 `["chat"]`。

**为什么不能承诺 100%：**

- DashScope 走的是 OpenAI 兼容接口，不一定走 `ProviderStrategy`（原生 JSON schema），更可能是 `ToolStrategy`（用 tool call 套 schema）。
- 模型仍可能漏字段、选空列表、或把挂号误判成问答。
- `min_length=1` 只能挡住「空列表」，挡不住「选错」。

可选加固（本轮可先不做）：

- [ ] 显式 `ToolStrategy(IntentDecision, handle_errors=True)`，校验失败让模型再试
- [ ] 规则兜底：出现「挂号 / 预约 / 医生 / 排班」等关键词时强制加上 `tools`

**实现选择（请选一个）：**

- [ ] **A（与现有 begin.py 一致）**：`create_agent` + `response_format`，无工具
- [ ] **B（更轻）**：`model.with_structured_output(IntentDecision)`，分类器不必做成 Agent

推荐 **A**，因为你已经在 `begin.py` 里用 `create_agent`，风格统一。分类器没有工具，多一层 Agent 循环的成本可以接受。

---



## 6. 三个业务节点的职责边界（先定边界，后写 prompt）


| 标记          | 节点           | 做什么                     | 不做什么            |
| ----------- | ------------ | ----------------------- | --------------- |
| `knowledge` | 专业知识问答 Agent | 基于知识库回答医疗/就诊常识          | 不挂号、不承诺诊断结论     |
| `chat`      | 普通聊天 Agent   | 寒暄、澄清、与业务无关的闲聊          | 不查号、不引用未检索的医学结论 |
| `tools`     | 工具调用 Agent   | 调 Java 内部工具：医生/科室/排班/挂号 | 不在工具结果之外编造号源    |


一条消息的典型切分：

- 「帮我挂明天内科，另外感冒要不要去医院？」→ `["knowledge", "tools"]`
- 「你好」→ `["chat"]`
- 「张医生下周还有号吗」→ `["tools"]`
- 「谢谢你啊，顺便问问儿科在几楼」→ `["knowledge", "chat"]`

- [ ] 同意上述边界
- [ ] 要改：________________

---



## 7. 落地 TODO（评估通过后再做）

骨架顺序建议如下。每一项都可以单独评审。

### 7.1 State 与 schema

- [ ] 把 `intent: str | None` 改成 `selected_agents: list[AgentName]`
- [ ] 增加 `knowledge_reply` / `chat_reply` / `tools_reply` / `final_reply`
- [ ] 新增 `IntentDecision` Pydantic 模型（可放 `app/graphs/hospital/schemas.py` 或 `begin.py` 旁）



### 7.2 起始节点

- [ ] `begin_agent` 加上 `response_format=IntentDecision`
- [ ] 写 `begin_node(state) -> dict`：调用 Agent，把 `selected_agents` 写回 State
- [ ] 解析失败重试 1 次，再失败兜底 `["chat"]`
- [ ] 结构化结果不要当对患者可见的回复塞进 `messages`



### 7.3 三个业务节点（先空壳）

- [ ] `knowledge.py`：无标记则 `return {}`
- [ ] `chat.py`：无标记则 `return {}`
- [ ] `tools.py`：无标记则 `return {}`
- [ ] 有标记时先返回一句占位回复，方便把图跑通



### 7.4 汇总节点 + 组图

- [ ] `merge.py`：按 `knowledge → chat → tools` 拼接非空回复到 `final_reply`，并追加一条 AI `messages`
- [ ] `graph.py`：`begin → knowledge → chat → tools → merge`
- [ ] 暂不接 FastAPI；先能本地 `graph.invoke(...)` 看 `selected_agents` 和跳过逻辑



### 7.5 验证用例（骨架期）

- [ ] 「你好」→ 只有 `chat` 有回复
- [ ] 「感冒吃什么药」→ 只有 `knowledge`
- [ ] 「帮我挂号」→ 只有 `tools`
- [ ] 「挂内科号，另外感冒要注意什么」→ `knowledge` + `tools` 都有回复，`chat` 跳过

---



## 8. 明确推迟

- 知识库检索、引用校验
- Java 工具客户端、挂号 interrupt / 幂等
- 并行 `Send`
- 用第二个 LLM 做回复润色
- 把 `begin` 做成带工具的 Agent（分类器不需要工具）

---



## 9. 评估后怎么回复我

直接回复这三件事即可开工：

1. 第 1 节哪些勾了、哪些要改
2. 起始节点选 **A** `create_agent` 还是 **B** `with_structured_output`
3. 执行顺序是否接受 **knowledge → chat → tools**

