# 温润在线医院 AI 模块流程骨架

> 以当前仓库代码为准。流程按职责拆成多张图：总览只展示跨服务主链路，复杂节点在各自章节展开。

## 1. AI 模块总览

这张图只回答“请求经过哪些系统”，不展开 LangGraph 内部判断。

```mermaid
flowchart LR
    U["患者请求"] --> J["Java AI 网关<br/>鉴权、会话归属、落库、执行锁"]
    J --> P["Python Chat API<br/>身份校验、图选择、SSE 编排"]
    P --> M{"运行模式"}
    M -->|正常模式| G["多 Agent graph"]
    M -->|快速模式| F["fast_graph"]
    G --> S["安全 SSE 输出"]
    F --> S
    S --> J
    J --> U2["患者接收 token / citation<br/>confirm / done / error"]

    J -.-> DB[("MySQL<br/>消息、业务数据、长期偏好")]
    J -.-> R[("Redis<br/>会话执行锁")]
    P -.-> R2[("Redis<br/>LangGraph checkpoint")]
    G -.-> C[("Chroma<br/>院内知识库")]
    G -.-> W["Web Search"]
    F -.-> W
    G -.-> L["模型服务"]
    F -.-> L
```

## 2. 请求入口与会话恢复

Java 负责可信业务边界，Python 只使用 Java 已验证的身份和有限恢复历史。委托令牌只进入本次 `HospitalToolContext`，不写入 LangGraph State 或 checkpoint。

```mermaid
flowchart TD
    A["浏览器调用 Java"] --> B["校验登录态、患者访问权、会话归属"]
    B --> C{"clientRequestId<br/>是否重复"}
    C -->|是| C1["返回已有结果或处理中"]
    C -->|否| D{"取得会话执行锁"}
    D -->|失败| D1["返回会话忙或锁服务不可用"]
    D -->|成功| E["保存 user 消息<br/>读取有限历史与长期偏好"]
    E --> F["签发最小权限委托 JWT"]
    F --> G["POST /v1/chat/stream"]

    G --> H["Python 校验 X-Api-Key<br/>与委托身份"]
    H --> I{"memoryEnabled 且<br/>Redis checkpointer 可用"}
    I -->|否| J["选择无状态图<br/>writes_enabled = false"]
    I -->|是| K["构造用户隔离 thread_id"]
    K --> L{"checkpoint 有消息"}
    L -->|是| M["恢复 checkpoint"]
    L -->|否，有恢复历史| N["用 Java 有限历史<br/>rehydrate checkpoint"]
    L -->|否，无恢复历史| O["使用本轮初始 State"]

    J --> P["构造 HospitalToolContext"]
    M --> P
    N --> P
    O --> P
    P --> Q{"fastMode"}
    Q -->|否| R["运行 normal graph"]
    Q -->|是| S["运行 fast_graph"]
```

## 3. 正常模式 graph

这张图对应 `graphs.py` 的真实拓扑，只展示节点之间的调度关系。`knowledge_node`、`tool_node` 等节点内部流程在后文展开。

```mermaid
flowchart TD
    START((START)) --> BEGIN["begin_node<br/>清空回合字段并选择 Agent"]
    BEGIN --> COUNT{"selected_agents<br/>数量至少为 2"}

    COUNT -->|否| DIRECT{"单意图直达"}
    DIRECT -->|knowledge| KNOW["knowledge_node"]
    DIRECT -->|chat| CHAT["chat_node"]
    DIRECT -->|tools| TOOL["tool_node"]

    COUNT -->|是| PLAN["plan_node<br/>拆子目标并判定依赖"]
    PLAN --> READY["条件边并行启动<br/>所有无依赖 Agent"]
    READY --> KNOW
    READY --> CHAT
    READY --> TOOL

    KNOW --> DEP{"tools 是否依赖<br/>knowledge"}
    DEP -->|是| TOOL
    DEP -->|否| FINAL["final_node<br/>defer = true"]
    CHAT --> FINAL
    TOOL --> FINAL

    FINAL --> SUM["summarize_node<br/>达到阈值时压缩历史"]
    SUM --> END((END))
```

调度要点：

- 单意图不经过 `plan_node`，直接进入对应 Agent。
- 多意图由 `plan_node` 为每个 Agent 生成独立 goal；规划失败时降级为全部并行。
- 当前依赖白名单只有 `tools → knowledge`，例如“判断该看哪科并挂对应科室”。
- `final_node` 使用 `defer=True`，等待并行分支和依赖链全部完成后只汇总一次。

## 4. begin_node 级联路由

`begin_node` 只分类，不直接回答患者。它优先使用确定性本地能力，仅在低置信、追问接续或本地无法判断时调用带历史上下文的 LLM。

```mermaid
flowchart TD
    A["读取最新用户消息<br/>构造受限路由上下文"] --> B["本地路由<br/>高精度规则 → 轻量分类器"]
    B --> C{"本地结果可接受"}

    C -->|是| D{"轻量结果且上一轮<br/>正在追问参数"}
    D -->|否| E["采用本地 selected_agents"]
    D -->|是| F["升级到带历史 LLM 分类"]
    C -->|否| F

    F --> G["模型调用失败时<br/>同请求最多重试一次"]
    G --> H{"JSON + Pydantic<br/>校验通过"}
    H -->|否，且有模型输出| I["要求模型修复 JSON 一次"]
    I --> J{"修复后有效"}
    H -->|是| K{"out_of_scope"}
    J -->|是| K
    J -->|否| L{"本地是否仍有标签"}
    H -->|否，且无模型输出| L

    L -->|是| M["采用本地标签<br/>lightweight_degraded"]
    L -->|否| N["回退 chat<br/>给出确定性澄清文案"]
    K -->|是| O["回退 chat<br/>给出服务范围说明"]
    K -->|否| P["规范化并去重标签"]

    E --> Q{"本地安全标志"}
    M --> Q
    N --> Q
    O --> Q
    P --> Q
    Q -->|有急症或自伤标志| R["强制加入 knowledge"]
    Q -->|无| S["保留分类结果"]
    R --> T["重置上一轮回复字段<br/>写入 selected_agents 与路由元数据"]
    S --> T
```

## 5. knowledge_node 知识路径

知识节点先走确定性安全判断，再查院内 RAG；只有院内资料未命中时才允许联网兜底。

```mermaid
flowchart TD
    A["进入 knowledge_node"] --> B{"selected_agents<br/>包含 knowledge"}
    B -->|否| Z["返回空更新"]
    B -->|是| C{"存在急症或<br/>自伤安全标志"}
    C -->|是| D["确定性急救提示<br/>不调用 RAG 或模型"]
    C -->|否| E["确定 query<br/>优先使用 planner goal"]
    E --> F{"query 是否为空"}
    F -->|是| G["请患者补充具体问题"]
    F -->|否| H["Chroma Retriever"]
    H --> I["过滤无效、不安全<br/>或过期资料"]
    I --> J{"院内资料命中"}
    J -->|是| K["基础模型流式回答<br/>只能依据院内资料"]
    K --> L["knowledge_reply<br/>+ rag_sources"]
    J -->|否| M["Web Agent 整理短检索词"]
    M --> N["调用 web_search"]
    N --> O["只依据网页片段回答<br/>附真实标题和链接"]
    O --> P["knowledge_reply<br/>rag_sources 为空"]
    M -. 联网失败 .-> Q["确定性服务降级文案"]
```

## 6. tool_node 与人工确认

Tool Agent 只能通过 Java 受控接口访问实时业务。无 checkpointer 或快速模式会关闭写工具，因此不会产生无法恢复的 `interrupt`。

```mermaid
flowchart TD
    A["进入 tool_node"] --> B{"selected_agents<br/>包含 tools"}
    B -->|否| Z["返回空更新"]
    B -->|是| C{"存在 delegated_token"}
    C -->|否| D["确定性降级<br/>业务查询暂不可用"]
    C -->|是| E{"writes_enabled"}
    E -->|否| F["只读 Agent<br/>科室、医生、排班、本人预约"]
    E -->|是| G["可写 Agent<br/>只读工具 + 挂号、退号、偏好"]

    F --> H["携带委托 JWT<br/>调用 Java Tool API"]
    G --> I{"是否调用写工具"}
    I -->|否| H
    I -->|是| J["先从 Java 读取权威对象<br/>并校验余号、过期、状态、归属"]
    J --> K["interrupt<br/>kind + prompt + detail"]
    K --> L["checkpoint 挂起<br/>SSE 发送 confirm，不发送 done"]

    L --> M["患者 approve / reject<br/>携带 interruptId"]
    M --> N["Java 重签委托 JWT<br/>POST /v1/chat/resume"]
    N --> O["校验 pending interrupt<br/>Command resume"]
    O --> P{"患者批准"}
    P -->|否| Q["不写业务数据"]
    P -->|是| R["调用 Java 受限写接口<br/>挂号幂等键保持稳定"]
    Q --> S["恢复原图并生成 tools_reply"]
    R --> S
    H --> T["生成 tools_reply"]
    S --> U["回到 final_node"]
    T --> U
```

## 7. 快速模式、上下文与输出

快速模式是一张独立小图，不经过意图路由、规划、院内 RAG 或 Java 业务工具。

```mermaid
flowchart LR
    START((START)) --> F["fast_node<br/>闲聊与公开医疗资料问答"]
    F --> W{"模型是否请求<br/>web_search"}
    W -->|是，最多 3 轮| S["web_search"]
    S --> F
    W -->|否| R["生成 final_reply"]
    R --> M["summarize_node"]
    M --> END((END))
```

正常图和快速图共用上下文压缩与 SSE 安全输出规则：

```mermaid
flowchart TD
    A["Context Builder"] --> B["可信系统策略"]
    A --> C["结构化 ConversationSummary"]
    A --> D["最近消息"]
    A --> E["最多 5 条长期偏好"]
    A --> F["当前子目标与可信边界内的上游结果"]

    G["节点执行产生 messages / values"] --> H["SSE 过滤器"]
    H --> I["隐藏嵌套 Agent 草稿、路由 JSON<br/>tool_calls 与工具原文"]
    I --> J{"选择患者可见正文"}
    J -->|单 chat| K["chat_node 分片"]
    J -->|单 knowledge 且 RAG 命中| L["knowledge_node 分片"]
    J -->|多意图、Tool 或联网兜底| M["final_node 分片"]
    J -->|快速模式| N["fast_node 分片"]
    K --> O["token / citation / confirm<br/>done / error"]
    L --> O
    M --> O
    N --> O
```

## 核心边界

- 浏览器只调用 Java，Java 再将 AI 请求转发给 Python。
- Python 负责模型调用、意图路由、RAG 和 Tool 编排，不直接读写挂号业务表。
- Python 调用业务工具时必须携带 Java 签发的委托 JWT。
- 用户身份和委托令牌只存在于 `HospitalToolContext`，不会进入 State 或 checkpoint。
- 挂号、退号和长期偏好写入必须经过 `interrupt → confirm → resume`。
- 快速模式只有 `web_search`，没有院内 RAG 和 Java 业务 Tool。

## 关键代码位置

| 模块 | 文件 |
| --- | --- |
| LangGraph 正常图与快速图 | `ai-python/app/graphs/hospital/graphs.py` |
| 级联意图路由 | `ai-python/app/graphs/hospital/nodes/begin.py`、`ai-python/app/intent/` |
| 多意图规划与依赖 | `ai-python/app/graphs/hospital/nodes/plan.py` |
| RAG 与网页兜底 | `ai-python/app/graphs/hospital/nodes/knowledge.py` |
| 业务 Tool Agent | `ai-python/app/graphs/hospital/nodes/tool.py` |
| 写操作确认 | `ai-python/app/graphs/hospital/tools/registration_write.py`、`memory.py` |
| 上下文与摘要 | `ai-python/app/graphs/hospital/context_builder.py`、`nodes/summarize.py` |
| SSE、checkpoint 恢复与 resume | `ai-python/app/api/routes/chat.py` |
| Java AI 网关 | `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java` |
| Java 内部 Tool API | `backend-java/src/main/java/com/wenrun/ai/controller/AiToolController.java` |
