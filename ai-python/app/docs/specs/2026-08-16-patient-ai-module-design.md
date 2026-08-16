# 患者端 AI 模块设计规格

日期：2026-08-16  
范围：`ai-python/app` 患者端 AI 能力，以及其与 `backend-java` 的联调契约。

## 1. 目标

使用 LangGraph 构建一个意图路由 Agent 和三个职责独立的业务 Agent：

1. 谈心聊天 Agent：处理问候、倾听、情绪陪伴和一般交流。
2. 医院个性化 Agent：结合医院专属 RAG 与 Java Tool，回答医院信息并协助患者办理业务。
3. 医疗知识 Agent：仅依据审核后的医疗知识库提供疾病、症状和日常护理科普。
4. 意图判断 Agent：识别请求属于 `chat`、`hospital` 或 `medical`，自身不直接回答。

首期面向患者端，完成“医院知识查询—排班号源查询—患者确认—创建挂号”的最小闭环。医生端、管理员端 AI 能力不在首期范围内。

## 2. 核心原则

- Python 不直接访问医院业务数据库，业务数据和业务写操作只能通过 Java API 获取或执行。
- 医院 Agent 可以在同一请求中组合医院 RAG 与多个 Java Tool。
- 医疗 Agent 不进行诊断、不开药、不提供处方或具体处方剂量。
- 诊断或开药类请求应自然说明能力边界，并继续提供安全的科普与就医建议；不使用机械固定文案。
- RAG 事实必须有资料来源，Tool 数据必须有接口来源与查询时间。
- 证据不足时明确说明知识库没有足够依据，不使用模型自身知识伪装成检索结论。
- 查询 Tool 可以直接执行；创建挂号等有副作用的 Tool 必须经过 HITL 确认。
- 会话记忆只在当前 `conversationId` 内有效，不跨会话召回。
- 患者原始令牌、委托令牌和其他密钥不得进入日志、Qdrant、聊天记录或 LangGraph checkpoint。

## 3. 总体架构

```text
Patient Web
    |
    v
backend-java（用户鉴权、业务校验、消息转发）
    |
    | X-Api-Key + 短期委托 JWT
    v
FastAPI
    |
    v
LangGraph 主图
    START
      -> 加载会话记忆
      -> 意图判断 Agent
           |-> chat     -> 谈心聊天 Agent
           |-> hospital -> 医院个性化 Agent
           |                 |-> 医院 RAG
           |                 |-> Java 查询 Tools
           |                 `-> 挂号 interrupt
           `-> medical  -> 医疗知识 Agent
                             `-> 医疗知识 RAG
      -> 引用与安全校验
      -> 保存会话记忆
      -> END
```

主图采用条件路由。医院 Agent 首期作为主图中的专用 Agent 节点，内部执行受限的“计划—调用—观察”循环；后续复杂度明显增加时，可在不改变主图路由契约的前提下迁移为独立子图。

## 4. Agent 职责

### 4.1 意图判断 Agent

输入当前用户消息及必要的短期上下文，输出结构化意图：

```text
chat | hospital | medical
```

- `chat`：问候、闲聊、倾听、情绪陪伴。
- `hospital`：医院位置、科室、医资、服务时间、挂号及其他院内办事。
- `medical`：疾病、症状、日常护理、健康科普及何时就医。

意图 Agent 只分类，不产生面向患者的答案。分类置信不足或请求含糊时，路由到澄清流程，而不是强行选择。

医院知识与挂号工具属于同一个 `hospital` 意图，使“外科在哪里，顺便帮我挂明天下午的号”可以在一次任务中完成。

### 4.2 谈心聊天 Agent

- 提供耐心、尊重、有同理心的日常交流。
- 不调用医院知识库、医疗知识库或业务 Tool。
- 不把聊天内容转化为诊断结论。
- 用户表达明确危险或紧急情况时，停止普通陪聊并建议及时联系急救或线下专业人员。
- 共情和一般对话不伪造资料引用。

### 4.3 医院个性化 Agent

可使用两类能力：

1. 医院 RAG：医院位置、科室分布、医资介绍、服务流程、挂号时间等静态或低频变化资料。
2. Java Tools：科室、医生、排班、实时号源查询及创建挂号。

Agent 先拆分任务，再补齐参数、执行检索或查询、汇总结果。静态 RAG 与实时 Tool 冲突时，以 Java Tool 的实时结果为准，并提示静态资料可能已更新。

首期 Tool：

- 查询科室；
- 查询医生；
- 查询排班及可用号源；
- 创建挂号。

取消挂号、缴费、检查、处方等能力列为后续事项。

### 4.4 医疗知识 Agent

- 只能基于 `medical-general` 知识库回答。
- 可解释常见原因、日常护理、生活注意事项、危险信号和何时就医。
- 不给出确定性诊断，不开药，不提供具体处方剂量。
- 患者要求诊断或开药时，必须以符合当前语境的自然表达说明没有诊断和开药权限，再提供安全范围内的帮助。
- 普通科普回答无需机械重复权限声明，但不得暗示已完成诊断。
- 出现胸痛、呼吸困难、意识异常等危险信号时，给出及时急诊或呼叫急救的建议，不输出确定性病名。

## 5. 医院 Agent 执行与兜底

典型复合请求：

```text
“外科在哪里，明天下午有哪些医生，帮我挂一个号”
```

执行步骤：

1. 从医院 RAG 检索外科位置。
2. 调用 Java Tool 查询明日下午排班与号源。
3. 在候选不唯一时让患者选择医生或号源。
4. 生成包含患者、科室、医生、日期、时段和费用的挂号摘要。
5. 调用 LangGraph `interrupt` 暂停，等待患者确认。
6. 恢复图后重新查询号源，防止确认期间数据变化。
7. 使用有写权限的新委托令牌调用创建挂号 Tool。
8. 返回挂号结果及可追溯的 Tool 来源。

必须覆盖以下兜底：

- 意图不明确：向患者澄清，不猜测操作目标。
- 参数缺失：逐步询问必要参数，不自行编造。
- RAG 无结果：说明知识库暂无可靠资料，并引导人工咨询。
- RAG 与 Tool 冲突：实时 Tool 数据优先。
- Java 不可用或 Tool 超时：不声称操作成功，保留非敏感任务状态并建议重试。
- 部分任务失败：分别说明已完成与未完成部分。
- 号源变化：返回新的可选号源，不擅自更换医生或时段。
- 重复请求：通过幂等键避免重复挂号。
- HITL 拒绝或超时：终止写操作，不创建挂号。
- 超出首期 Tool 范围：明确说明暂不支持，并引导患者使用现有页面或人工服务。
- Agent 循环超限：停止自动调用并安全降级，不无限重试。

## 6. LangGraph State 与记忆

### 6.1 State

业务 State 包含：

- `messages`
- `conversation_id`
- `user_id`
- `patient_id`
- `intent`
- `memory_enabled`
- `task_plan`
- `tool_context`
- `sources`
- `pending_action`
- `error`
- `retry_count`

运行时凭据单独通过请求上下文注入，不属于业务 State。

### 6.2 三层记忆

1. 短期窗口：按 token 预算保留最近消息，保障代词、多轮追问和参数补全的连续性。
2. 会话摘要/向量记忆：将被窗口淘汰的重要内容摘要或提取为关键事实，写入独立 Qdrant collection。
3. 结构化任务状态：挂号参数、候选项和待确认操作存入 LangGraph checkpoint，不通过向量检索猜测恢复。

默认短期窗口预算由配置项控制；超出预算时保留最近消息并摘要较早内容。向量记忆检索必须使用 `conversationId` 等值过滤。

### 6.3 数据隔离

```text
wenrun_hospital_custom     医院专属知识
wenrun_medical_general     医疗科普知识
wenrun_conversation_memory 当前会话摘要记忆
LangGraph checkpoint       图状态与 interrupt
```

- 三类向量数据不得混合检索。
- `memoryEnabled=false` 时不读取或写入向量记忆，但允许使用完成当前请求所需的临时 State。
- 新建会话不召回旧会话。
- 删除会话时删除对应向量记忆和 checkpoint。
- 首期使用持久化 checkpointer，并通过存储接口隔离具体实现；本地开发采用 SQLite 文件及专用数据卷，单进程运行。横向扩容前必须切换为支持并发的共享 checkpoint 存储。

## 7. RAG 设计

### 7.1 可信资料

只允许管理员审核后的权威资料进入医院或医疗知识库，例如医院正式资料、诊疗指南和正规医学科普。首期不允许 AI 自主联网搜索，也不允许普通患者上传资料。

管理员上传页面及完整 Java 管理流程暂不实施。Python 保留受内部 API Key 保护的 Word/PDF 入库接口，开发阶段通过 Swagger 或 cURL 调用。

### 7.2 入库

```text
Word/PDF
  -> 文件类型、大小和内容校验
  -> 文本及标题/页码提取
  -> 按标题、段落和页码切片
  -> 清洗并补全元数据
  -> 向量化
  -> 写入指定 collection
```

每个切片至少包含：

- `documentId`
- `knowledgeBase`
- `originalName`
- `pageNumber` 或章节标题
- `chunkIndex`
- `content`
- `documentVersion`
- `ingestedAt`

同一 `documentId` 重复入库采用幂等替换。新版本全部写入成功后再替换旧版本；失败时清理本次数据，避免半份文档。

### 7.3 检索

- 医院 Agent 只能检索医院知识库。
- 医疗 Agent 只能检索医疗知识库。
- 先语义召回，再按相关性阈值过滤。
- 医院名、科室名、医生名等精确实体可补充关键词匹配。
- 检索结果必须包含可展示的来源元数据。
- 没有足够相关证据时返回保守答案，不让模型使用未检索知识补齐事实。

### 7.4 引用

检索片段在生成上下文中编号为 `[S1]`、`[S2]`。事实性句子引用对应编号，最终响应返回结构化来源：

```json
{
  "id": "S1",
  "documentId": "doc-123",
  "title": "医院门诊服务指南",
  "page": 6,
  "section": "挂号时间",
  "excerpt": "门诊挂号时间为……"
}
```

Tool 来源包含工具名称、查询时间和安全化结果摘要，不暴露内部 URL、令牌或调试参数。

引用校验节点检查：

- 引用是否存在；
- 引用片段是否支持对应结论；
- 是否出现无引用的医院或医疗事实；
- 是否混用错误知识库；
- Tool 数据是否被错误改写。

校验失败时最多重写一次；仍失败则返回保守答案。

## 8. HITL 与挂号安全

查询 Tool 无副作用，可直接执行。创建挂号必须经过 LangGraph `interrupt`：

```text
收集参数
  -> 查询实时号源
  -> 生成挂号摘要
  -> interrupt
  -> 患者确认/拒绝/修改
  -> 使用新凭据恢复
  -> 再次检查号源
  -> 创建挂号
```

`interrupt` 数据包含一次性 `interruptId`、操作类型、待确认参数和对患者可见的摘要。

安全要求：

- `interruptId` 必须绑定 `conversationId` 和当前患者。
- 同一个 `interruptId` 只能成功恢复一次。
- 拒绝、超时或参数被篡改时不得执行写操作。
- 创建挂号使用稳定幂等键。
- Java 在写入前重新校验患者、排班、号源、重复挂号及其他业务约束。
- LLM 输出不能绕过 Java 业务校验。

## 9. Java 与 Python 联调及鉴权

### 9.1 调用方向

```text
Browser -> Java -> Python -> Java AI Tool API -> MySQL
```

Python 不直接连接业务 MySQL。

### 9.2 两层服务认证

1. Java 调 Python：使用内部 `X-Api-Key`。
2. Python 调 Java Tool：使用 Java 签发的短期、限权委托 JWT。

委托 JWT 至少包含：

- `userId`
- `patientId`
- `conversationId`
- `aud=ai-tools`
- `scope`
- `exp`
- `jti`

默认有效期为 2 至 5 分钟，由 Java 配置。Java 必须校验签名、受众、有效期、scope 和患者身份，以令牌声明为准，不信任 LLM 传入的 `patientId`。

初始聊天请求只签发查询 scope：

- `dept:read`
- `doctor:read`
- `schedule:read`

患者确认恢复时，Java 重新签发短期令牌并增加 `registration:create`，同时绑定 `interruptId`。这样写权限只在患者确认后出现。

委托 JWT 仅存在于 FastAPI 请求运行时上下文。interrupt 恢复必须由患者重新经过 Java 发起，以获得新令牌。

### 9.3 Java Tool 白名单

Python 只能调用 `/api/internal/ai-tools/**`：

- 科室查询；
- 医生查询；
- 排班/号源查询；
- 创建挂号。

Java 返回稳定业务错误码，例如：

- `SCHEDULE_NOT_FOUND`
- `SLOT_SOLD_OUT`
- `DUPLICATE_REGISTRATION`
- `INVALID_PATIENT`
- `INSUFFICIENT_SCOPE`

Agent 根据错误码走确定性兜底，不解析异常文本猜测结果。

## 10. FastAPI 契约

### 10.1 服务接口

- `GET /health`
- `POST /v1/chat`
- `POST /v1/chat/stream`
- `POST /v1/chat/resume/stream`
- `POST /v1/knowledge/ingest`
- `DELETE /v1/knowledge/{knowledgeBase}/{documentId}`

除部署环境允许公开的健康检查外，其余接口均要求内部 API Key。

### 10.2 聊天请求

```json
{
  "message": "帮我挂明天下午的内科",
  "conversationId": "uuid",
  "memoryEnabled": true,
  "userContext": {
    "userId": 1,
    "patientId": 10
  }
}
```

委托 JWT 通过专用请求头传递，不放入聊天 JSON、State 或可持久化对象。

`conversationId` 同时作为 LangGraph `thread_id`。Java 校验其属于当前登录患者。

### 10.3 SSE 事件

- `status`：当前阶段，如路由、检索、查询号源。
- `token`：可展示的流式文本。
- `citation`：结构化资料或 Tool 来源。
- `interrupt`：待确认操作。
- `done`：最终回答、意图和完整来源。
- `error`：稳定错误码及可安全展示的信息。

发生 `interrupt` 后，本次流正常结束，不发送伪完成的挂号结果。

### 10.4 恢复请求

恢复请求包含：

- `conversationId`
- `interruptId`
- `approved`
- 患者修改后的可选参数

Java 验证登录患者和会话归属，签发新委托令牌，再调用 Python。Python 使用 LangGraph `Command(resume=...)` 恢复图。

## 11. 错误处理与可观测性

- 外部错误响应不返回堆栈、Prompt、内部 URL、密钥或患者敏感资料。
- 日志按 `requestId`、`conversationId`、Agent、节点和 Tool 关联，但对患者信息脱敏。
- 记录意图路由、检索耗时、Tool 耗时、引用校验、interrupt 和错误码。
- 不记录原始 JWT、委托 JWT、API Key 或完整过敏史等敏感上下文。
- LLM、Qdrant 和 Java Tool 均设置超时和有限重试；写操作不做无幂等保护的自动重试。
- Agent Tool 循环设置最大步数，引用校验只允许一次重写。

## 12. 测试与验收

### 12.1 单元测试

- 三类意图及含糊意图路由。
- State 更新、窗口裁剪、摘要及 `memoryEnabled=false`。
- 两类知识库过滤和会话记忆过滤。
- 医疗能力边界及危险信号提示。
- 引用存在性、支持关系和知识库隔离校验。
- Tool 错误码到患者提示的映射。

### 12.2 图集成测试

使用假 LLM、假 Qdrant 和假 Java API，覆盖：

- 谈心聊天；
- 医院 RAG 单独回答；
- 医院 RAG 与 Tool 复合请求；
- 医疗 RAG 科普；
- 空检索结果；
- Tool 超时及部分失败；
- 最大 Agent 步数；
- interrupt、拒绝、修改、确认及恢复；
- 确认后号源变化；
- 重复恢复和幂等挂号。

### 12.3 契约与端到端测试

- Java/Python 请求模型、SSE 事件和错误码一致。
- 无 API Key、无效委托 JWT、过期令牌和 scope 越权被拒绝。
- 用户不能访问其他患者的会话或 interrupt。
- Word/PDF 入库、重复入库、失败回滚、检索和删除。
- 医院、医疗、记忆三个 collection 不发生交叉召回。
- 所有医院/医疗事实有有效来源。
- 患者确认前不会创建挂号；确认后 Java 仍执行最终业务校验。

## 13. 首期非目标与后续事项

首期不实现：

- 医生端 AI 能力；
- 管理员端 AI 页面及完整上传管理流程；
- 普通用户上传知识资料；
- AI 自主联网搜索；
- 取消挂号、缴费、检查和处方 Tool；
- 跨会话长期记忆；
- 医疗诊断、开药和具体处方剂量；
- Python 直接访问业务数据库；
- 多实例共享 SQLite checkpoint。

后续可在不改变三类意图契约的前提下，将复杂 Agent 节点迁移为子图，增加管理员知识审核流程、更多患者业务 Tool，以及支持横向扩容的共享 checkpoint 存储。

## 14. 完成标准

满足以下条件视为首期完成：

1. 主图稳定路由三个业务 Agent。
2. 医院 Agent 可组合医院 RAG 与 Java 查询 Tool。
3. 患者可通过 HITL 确认完成一次真实挂号，且不存在未确认写入。
4. 医疗 Agent 仅做有来源的安全科普，并自然表达诊断和开药边界。
5. 事实性医院/医疗回答与 Tool 数据均可追溯。
6. 记忆只在当前 `conversationId` 内召回。
7. Python 只通过受鉴权的 Java Tool API 获取和修改业务数据。
8. 关键单元、图集成、契约和端到端测试通过。
