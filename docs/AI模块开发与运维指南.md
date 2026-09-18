# AI 模块开发与运维指南

本文面向温润在线医院项目的开发、联调和部署人员，说明患者端 AI 助手的组成、配置、接口协议、知识库维护方式及当前边界。实现以仓库当前代码为准。

## 1. 模块职责与调用链

AI 能力不是由浏览器直接调用 Python 服务，而是经 Java 网关统一鉴权和转发：

```text
Vue 前端
  │  Bearer Token + clientRequestId
  ▼
Java /api/ai/chat/stream
  ├─ 校验登录态、会话归属和请求幂等性
  ├─ 保存用户消息 / 在完成后保存助手消息
  └─ X-Api-Key + 短期委托 JWT + X-Request-Id
       ▼
FastAPI /v1/chat/stream
  ├─ LangGraph 意图路由、知识检索和回复汇总
  ├─ Redis checkpoint/会话锁，checkpoint miss 时从 MySQL 恢复有限历史
  ├─ MySQL 文档生命周期元数据 + Chroma 可重建向量索引
  └─ Tavily（院内知识未命中时的可选网页检索）
```

关键目录如下：

| 位置 | 职责 |
| --- | --- |
| `ai-python/app/api/routes/chat.py` | Python 内部聊天 SSE 与知识库上传接口 |
| `ai-python/app/graphs/hospital/` | LangGraph 状态、节点、提示词与联网工具 |
| `ai-python/app/rag/` | Chroma 本地索引、Embedding 与文档入库 |
| `backend-java/.../ai/` | Java 鉴权后的 AI 网关、SSE 转发、会话幂等控制 |
| `frontend/src/api/modules/ai.js` | 浏览器端 SSE 读取、事件解析和删除会话调用 |
| `frontend/src/composables/useAssistant.js` | 跨页面保活的前端对话运行状态 |

浏览器不得保存或发送 `AI_SERVICE_API_KEY`，也不应直接调用 `:8000` 的 Python 接口。

## 2. 启动前配置

### 2.1 配置文件

根目录 `.env` 由 [`.env.example`](../.env.example) 复制而来，至少需要设置：

```dotenv
# Java 调用 Python 的地址；本地分别启动时使用 http://localhost:8000
AI_SERVICE_BASE_URL=http://ai-python:8000

# 随机生成的服务间密钥，必须与 ai-python/.env 中的值完全一致
AI_SERVICE_API_KEY=请替换为高强度随机字符串

# MySQL 配置（Docker Compose 必需）
MYSQL_ROOT_PASSWORD=请替换为数据库密码
RAG_METADATA_MYSQL_PASSWORD=请与上面的密码保持一致；生产建议改用受限账号
```

AI 服务配置由 `ai-python/.env` 提供，可从 [`ai-python/.env.example`](../ai-python/.env.example) 复制：

```dotenv
# 使用 OpenAI 兼容协议的聊天与向量模型
DASHSCOPE_API_KEY=模型服务密钥
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=聊天模型名称
EMBEDDING_MODEL=向量模型名称

# 级联意图路由；默认值见 ai-python/.env.example
INTENT_LIGHTWEIGHT_ENABLED=true
INTENT_LABEL_THRESHOLD=0.50
INTENT_ACCEPTANCE_THRESHOLD=0.60
INTENT_AMBIGUITY_MARGIN=0.12
INTENT_OOD_SIMILARITY_THRESHOLD=0.08

# Chroma：进程内持久化目录，空则默认 ai-python/data/chroma
CHROMA_PERSIST_DIR=
CHROMA_HOSPITAL_COLLECTION=wenrun_hospital_custom

# checkpoint、上下文预算与知识文档元数据
AI_REDIS_URL=redis://redis:6379/0
AI_CHECKPOINT_TTL_MINUTES=1440
RAG_METADATA_MYSQL_HOST=mysql
RAG_METADATA_MYSQL_DATABASE=wenrun
RAG_METADATA_MYSQL_USER=root
RAG_METADATA_MYSQL_PASSWORD=与根目录一致的数据库密码

# 必须等于根目录的 AI_SERVICE_API_KEY
AI_INTERNAL_API_KEY=与根目录一致的服务间密钥

# Python Tool 调用 Java 的内部地址；本地分别启动时使用 http://localhost:8080
JAVA_TOOL_BASE_URL=http://backend-java:8080
JAVA_TOOL_TIMEOUT_SECONDS=5

# 可选：院内知识未命中时，启用公开网页检索
TAVILY_API_KEY=
```

注意事项：

- 本地直接运行 Python 时，默认把索引写到 `ai-python/data/chroma`；Docker 应设置 `CHROMA_PERSIST_DIR=/app/data/chroma` 并挂载数据卷。
- 入库和检索必须使用同一个 `EMBEDDING_MODEL`。更换模型或向量维度时，应清空 Chroma 目录并重新导入资料，不能复用旧索引。
- Chroma 运行在 Python 进程内，不再需要独立向量库容器或 API Key。
- `JAVA_TOOL_BASE_URL` 只能指向 Java 的内网地址。Python 不直接查询或修改 HIS 业务表；业务 Tool 必须经过 Java。唯一的直连例外是 `ai_knowledge_documents` 文档生命周期登记表，生产账号应只授予该表所需权限。
- `.env` 含密钥，已被 Git 忽略，不得提交。

### 2.2 启动方式

完整容器化启动：

```powershell
Copy-Item .env.example .env
Copy-Item ai-python/.env.example ai-python/.env
# 填写两个文件，并确保两处服务间密钥一致
docker compose up --build
```

分别启动时，先启动 MySQL 和 Python，再启动 Java 与前端：

```powershell
cd ai-python
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --reload
```

```powershell
cd backend-java
$env:AI_SERVICE_BASE_URL = 'http://localhost:8000'
$env:AI_SERVICE_API_KEY = '与 ai-python/.env 一致的密钥'
mvn spring-boot:run
```

Python 存活探针为 `GET http://localhost:8000/health`，返回 `{"status":"ok"}`。该接口不要求内部密钥；其他 Python API 均要求 `X-Api-Key`。

## 3. 接口与 SSE 协议

### 3.1 浏览器调用的 Java 接口

`POST /api/ai/chat/stream`

请求需要正常登录态；请求体为 JSON（`Content-Type: application/json`），响应为 SSE（`Content-Type: text/event-stream`）：

```json
{
  "message": "感冒后需要注意什么？",
  "conversationId": "可选、最长 64 字符",
  "clientRequestId": "建议每次发送均生成 UUID",
  "memoryEnabled": true
}
```

- `message` 必填，最长 2,000 字符。
- 缺省的 `conversationId` 和 `clientRequestId` 会由 Java 生成；前端应主动生成稳定的 `clientRequestId`，以便网络重试和跨页面恢复时保持幂等。
- Java 从当前登录用户补充 `userId` 与绑定的 `patientId`，忽略浏览器试图伪造的同名字段。
- 同一用户、会话、请求 ID 的同一轮消息只会创建一次：完成后重试会返回已保存回复；仍在处理中会收到 `AI_REQUEST_IN_PROGRESS`；若同一 ID 对应不同消息则返回 `AI_REQUEST_ID_REUSED`。

`DELETE /api/ai/conversations/{conversationId}` 用于删除当前用户拥有的会话消息。不存在的会话按成功处理，其他用户的会话会返回拒绝访问。

`POST /api/ai/chat/resume` 用于提交患者对写操作确认卡片的选择并恢复 SSE；请求体为 `{"conversationId": "...", "decision": "approve" | "reject", "clientRequestId": "..."}`。

### 3.2 Java 到 Python 的内部接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | Python 存活检查，不鉴权 |
| `POST` | `/v1/chat/stream` | 内部对话 SSE，需要 `X-Api-Key` |
| `POST` | `/v1/chat/resume` | 内部恢复确认后的对话 SSE，请求体为 `{"conversationId": "...", "decision": "approve" | "reject", "clientRequestId": "..."}` |
| `POST` | `/v1/chat/documents` | 上传资料并写入 RAG，需要 `X-Api-Key` |

Python 的聊天请求使用驼峰字段：`message`、`conversationId`、`memoryEnabled`、`userContext.userId`、`userContext.patientId`。Java 会透传 `X-Request-Id`，Python 日志会复用或生成该追踪号。

`/v1/chat/documents` 是 Python 内部管理接口，使用 `multipart/form-data` 的 `file` 字段。当前 Java 尚未提供对应的管理端代理接口，因此不要把该地址直接暴露给普通浏览器用户。

### 3.3 SSE 事件

事件以 `data: {JSON}\n\n` 发送，前端按 `type` 消费：

| `type` | 主要字段 | 含义 |
| --- | --- | --- |
| `status` | `content` | 处理阶段提示，如“正在分析您的问题…” |
| `token` | `content` | 可直接追加到答案的正文片段 |
| `citation` | `sources` | RAG 命中资料的元数据数组 |
| `confirm` | 写操作等待患者确认，本次流到此结束，不再发 `done`。字段：`conversationId`、`kind`（`registration_create` / `registration_cancel`）、`prompt`、`detail` | 前端渲染确认卡片，患者选择后调 `POST /api/ai/chat/resume` |
| `done` | `reply`、`conversationId`、`selectedAgents`、`sources` | 正常结束及完整结果 |
| `error` | `code`、`message` | 调用失败或幂等冲突 |

`token` 可能为空缺：例如上游不提供增量片段时，Python 会在结束前一次发送完整 `reply`。调用方必须以 `done.reply` 作为最终兜底文本，不能仅依赖 token 拼接。

### 3.3 Python 到 Java 的内部 Tool 接口

Python Tool 使用 Java 在调用聊天时签发的短期委托 JWT，调用 Java 的受控业务接口；浏览器不能访问或伪造此 Token。

| 方法 | 路径 | 权限 | 当前用途 |
| --- | --- | --- | --- |
| `GET` | `/api/internal/ai-tools/departments?status=1` | `departments:read` | 查询启用的科室，验证 Python Tool → Java → MySQL 通信 |

请求头使用 `Authorization: Bearer {delegated-jwt}`，并透传 `X-Request-Id`。Java 会重新校验签名、过期时间、用户/患者身份和 scope；接口不接受 SQL、表名或由模型自由拼接的查询条件。

Java 的单条流默认最长 300 秒；Java 到 Python 的默认连接超时为 5 秒、读取超时为 300 秒，可用 `AI_SERVICE_CONNECT_TIMEOUT_MILLIS` 与 `AI_SERVICE_READ_TIMEOUT_MILLIS` 调整。

## 4. 对话工作流

正常模式的路由与并行分发如下：

```text
输入 → 高精度规则 → 轻量分类器 →（不确定时）LLM 分类
                                      ↓
START → begin_node ─┬→ knowledge_node ─┐
                    ├→ chat_node ───────┼→ final_node → summarize_node → END
                    └→ tool_node ───────┘
```

`begin_node` 选中的节点会并行分发；多意图全部完成后才进入 `final_node`。

1. `begin_node` 先用高精度规则处理明确请求，再用字符 TF-IDF + One-vs-Rest Logistic Regression 做 CPU 轻量多标签分类。只有低置信度、Top-1/Top-2 歧义或域外样本才升级到 LLM。
2. LLM 将最新请求识别为 `knowledge`、`chat`、`tools` 的一个或多个标签，也可以显式返回 `out_of_scope`。输出经 Pydantic 校验；结构异常时修复一次，仍失败则输出确定性澄清，不再让闲聊模型猜测。
3. 路由把阶段、分数、命中规则、升级原因、安全信号和模型版本写入 `State.intent_route` 与日志。`GET /v1/metrics/intent-routing` 可在携带内部 API Key 时查看当前进程计数。
4. 急症正则是独立安全维度，会强制保留 `knowledge`；`knowledge_node` 对命中的安全信号直接给出确定性急救提示，不依赖 Chroma、网页或另一轮模型。
5. `knowledge_node` 在普通 `knowledge` 请求中优先检索院内 Chroma。命中时只允许依据院内片段回答；未命中时调用带 Tavily 工具的联网 Agent。
6. `chat_node` 处理问候、感谢和非医疗闲聊；`tool_node` 处理本院实时业务和受控写工具。
7. `final_node` 收集回复。只有一个回复时原样输出；多个回复才调用模型合并，失败时确定性拼接。
8. `fastMode=true` 时整张图被替换为 `START → fast_node → summarize_node → END`。它不运行级联路由，没有院内 RAG，也查不了号源排班。

为避免把路由 JSON、工具参数或检索原文泄漏给患者，SSE 只转发根图节点的模型分片，嵌套 Agent（`ns` 非空的子图）分片一律丢弃。单意图时直接流出该节点自身的正文：纯闲聊来自 `chat_node`，纯知识来自 `knowledge_node` 的 RAG 命中分支。多意图请求由 `final_node` 重写正文，只流出 `final_node`。`tool_node` 与知识的 Tavily 兜底走嵌套 Agent，当前不流式，等 `final_node` 透传后一次性下发。快速模式下 token 只来自 `fast_node`。

### 当前功能边界

- `tools` 已接入科室、医生、排班、本人挂号查询，以及挂号/退号写操作。写操作先由 `interrupt` 返回确认卡片，患者携带对应 `interruptId` 恢复后，Java 再校验患者身份、写 scope、幂等键和业务约束。
- `memoryEnabled` 已生效。为 `true` 且 `AI_REDIS_URL` 可用时，图使用 Redis checkpointer；实际 key 是 `user:{verifiedUserId}:conversation:{conversationId}`，不能仅用前端传入的会话 ID。超过消息数或 token 阈值后写入结构化摘要并裁剪旧消息。
- checkpoint miss 时，Java 会提供 MySQL 中有限、已归属校验的历史窗口用于重建上下文；Redis 故障或用户关闭记忆时退化为当前轮上下文，MySQL 消息仍是历史事实源。
- 长期记忆只允许患者显式确认的沟通、预约和无障碍偏好。Python 通过受限 Tool 访问 Java，症状、诊断、药物、剂量、过敏等医疗事实会被 Java 拒绝写入。
- 委托令牌不进入 State，只通过 Runtime Context（`HospitalToolContext`）传递，不会写入 checkpoint。
- 删除会话时，Java 会调用 `DELETE /v1/chat/memory/{conversationId}` 级联清理 checkpoint。
- 同一会话有 Redis 分布式锁；并发请求不会同时修改 checkpoint，锁不可用时保守返回 busy，而不是无锁执行。

扩展业务工具时，应先在 Java 定义经过鉴权和参数校验的受控业务能力，再把对应工具注册到图中；禁止让模型直连数据库或以模型文本直接执行写操作。涉及挂号、取消等写操作时，应使用确认步骤、幂等键和审计日志。

## 5. 知识库维护

### 5.1 支持的文件与处理方式

上传接口支持 `.pdf`、`.docx`、`.txt`、`.md`、`.markdown`：

1. PDF 按页提取文本；扫描版 PDF 没有 OCR，提取不到文本会失败。
2. DOCX 只读取普通段落，不读取表格、图片或嵌入对象。
3. TXT/Markdown 优先按 UTF-8（含 BOM）解码，失败后使用 GB18030。
4. 文本按 800 字符切分、120 字符重叠，使用 Embedding 写入 Chroma。
5. 检索返回相似度达到 `0.8` 的最多 5 个片段；命中资料会作为 `citation` 发给前端。

通过受保护的内部地址上传示例：

```powershell
$headers = @{ 'X-Api-Key' = '服务间密钥' }
Invoke-RestMethod `
  -Uri 'http://localhost:8000/v1/chat/documents' `
  -Method Post `
  -Headers $headers `
  -Form @{ file = Get-Item '.\医院就诊须知.docx' }
```

成功响应包含 `document_id`、`version`、`checksum`、`status`、`filename` 与 `chunk_count`。建议在导入前对资料进行人工审核，特别是院内地址、楼层、就诊时间和收费说明。

### 5.2 生命周期管理

- 同一 `documentId` + checksum 默认幂等；`forceRebuild` 或 `/documents/{id}/rebuild` 创建下一版本。新版本完整写入后，旧 active 版本才变为 `superseded`。
- `GET /v1/chat/documents/{id}` 查看版本；`POST .../{id}/deactivate` 停用；`DELETE .../{id}` 删除全部向量点。MySQL 配置后是元数据权威源，Chroma 是可重建索引；发布、停用和删除失败会执行补偿或标记 `reconcile_required`。
- 每个 chunk 带版本、有效期、更新时间和稳定 chunk ID。检索在 Chroma 侧过滤 `active` 与有效期，并在送入模型前再次 fail-closed 检查、限长、清理控制字符和拒绝疑似提示注入片段。
- 引用包含 document ID、version、page、chunk ID 和 updated time。原始上传文件当前不做对象存储归档；需要灾备时必须另行保存源文件，才能从 MySQL 元数据重建 Chroma。

## 6. 数据安全与可观测性

- Java 负责浏览器身份认证和会话所有权；Python 仅信任携带共享 `X-Api-Key` 的内部调用。服务间密钥必须足够随机并定期轮换。
- Docker Compose 将 Python 的 8000 端口映射到宿主机。生产环境应限制该端口的网络访问，优先仅允许 Java 网关访问。
- 模型提示词明确禁止诊断、处方、编造院内数据和医疗承诺。急症或明确危险场景要求建议立即急救/急诊，但这不是临床安全体系的替代品。
- Python 中间件为每个请求记录 `request_id`、方法、路径、状态和耗时；日志过滤会脱敏 `Authorization`、`X-Api-Key` 等敏感头。排障时可用 Java 与 Python 的 `X-Request-Id` 关联同一请求。
- 每轮额外输出 `context_trace`：哈希 thread、模式、checkpoint/rehydration 状态、按来源 token、摘要版本、记忆/RAG 数、工具名、首 token/总耗时、错误码及 prompt/schema 版本。默认从不采集患者原文、访问令牌、完整 RAG 或工具返回；`GET /v1/metrics/context` 只返回当前进程的低基数聚合。
- 用户消息在发起上游流前落库；收到 `done` 后才保存助手消息。上游中断后可能只保留用户消息，应以 SSE `error` 事件向患者说明重试状态。

## 7. 测试与排障

基础验证命令：

```powershell
cd ai-python
python -m pytest
python scripts/evaluate_intent_router.py
python scripts/evaluate_context.py

cd ../backend-java
mvn test

cd ../frontend
npm test
npm run lint
npm run build
```

常见问题排查顺序：

| 现象 | 优先检查项 |
| --- | --- |
| Java 返回“无法连接 AI 流式服务” | Python 是否存活、`AI_SERVICE_BASE_URL` 是否可达、Docker 网络/端口是否正确 |
| Python 返回 401 | 根目录 `AI_SERVICE_API_KEY` 与 `AI_INTERNAL_API_KEY` 是否完全一致，Java 是否发送 `X-Api-Key` |
| 资料上传/检索失败 | `CHROMA_PERSIST_DIR` 是否可写、Embedding 三项配置、collection 与模型维度是否匹配 |
| 总是走网页或提示知识库不可用 | Chroma 是否有资料、相似度阈值 `0.8` 是否过高、Tavily 密钥和外网是否可用 |
| 流式答案重复或不完整 | 前端是否为同一轮复用 `clientRequestId`、检查 `done.reply`、用 `X-Request-Id` 对照 Java/Python 日志 |
| 正常模式“挂号/查排班”没有实际结果 | 检查委托 JWT scope、患者绑定、Java 内部 Tool API 与 Redis checkpoint；写操作必须先收到 `confirm` 再携带同一 `interruptId` 调 `/resume` |
| 快速模式答不出号源排班或本院楼层/须知 | 这是设计行为，不是故障。快速模式只有闲聊、联网和记忆，请关闭快速模式重问 |

相关实现可从 [`ai-python/README.md`](../ai-python/README.md) 和 [`aiController.java`](../backend-java/src/main/java/com/wenrun/ai/controller/aiController.java) 继续阅读。
