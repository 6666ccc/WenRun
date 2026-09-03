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
  └─ X-Api-Key + X-Request-Id
       ▼
FastAPI /v1/chat/stream
  ├─ LangGraph 意图路由、知识检索和回复汇总
  ├─ Qdrant 院内知识库
  └─ Tavily（院内知识未命中时的可选网页检索）
```

关键目录如下：

| 位置 | 职责 |
| --- | --- |
| `ai-python/app/api/routes/chat.py` | Python 内部聊天 SSE 与知识库上传接口 |
| `ai-python/app/graphs/hospital/` | LangGraph 状态、节点、提示词与联网工具 |
| `ai-python/app/rag/` | Qdrant 连接、Embedding 与文档入库 |
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
```

AI 服务配置由 `ai-python/.env` 提供，可从 [`ai-python/.env.example`](../ai-python/.env.example) 复制：

```dotenv
# 使用 OpenAI 兼容协议的聊天与向量模型
DASHSCOPE_API_KEY=模型服务密钥
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=聊天模型名称
EMBEDDING_MODEL=向量模型名称

# Qdrant；Compose 没有创建 Qdrant，需要单独启动或使用已有实例
QDRANT_URL=http://host.docker.internal:6333
QDRANT_HOSPITAL_COLLECTION=wenrun_hospital_custom

# 必须等于根目录的 AI_SERVICE_API_KEY
AI_INTERNAL_API_KEY=与根目录一致的服务间密钥

# Python Tool 调用 Java 的内部地址；本地分别启动时使用 http://localhost:8080
JAVA_TOOL_BASE_URL=http://backend-java:8080
JAVA_TOOL_TIMEOUT_SECONDS=5

# 可选：院内知识未命中时，启用公开网页检索
TAVILY_API_KEY=
```

注意事项：

- 本地直接运行 Python 时，`QDRANT_URL` 通常应改为 `http://localhost:6333`；Docker 容器访问宿主机才使用 `host.docker.internal`。
- 入库和检索必须使用同一个 `EMBEDDING_MODEL`。更换模型或向量维度时，应新建 collection 并重新导入资料，不能复用旧 collection。
- `QDRANT_TIMEOUT` 目前仅存在于示例配置；代码中的连接超时固定为 10 秒。
- 当前 Qdrant 客户端未传入 API Key，生产环境应通过私有网络、反向代理或后续代码改造保护 Qdrant。
- `JAVA_TOOL_BASE_URL` 只能指向 Java 的内网地址。Python 不直接连接 MySQL；所有业务数据查询和写入必须经过 Java 内部 Tool API。
- `.env` 含密钥，已被 Git 忽略，不得提交。

### 2.2 启动方式

完整容器化启动：

```powershell
Copy-Item .env.example .env
Copy-Item ai-python/.env.example ai-python/.env
# 填写两个文件，并确保两处服务间密钥一致
docker compose up --build
```

分别启动时，先启动 Qdrant、MySQL 和 Python，再启动 Java 与前端：

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

### 3.2 Java 到 Python 的内部接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | Python 存活检查，不鉴权 |
| `POST` | `/v1/chat/stream` | 内部对话 SSE，需要 `X-Api-Key` |
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

当前 LangGraph 的固定顺序如下：

```text
START → begin_node → knowledge_node → chat_node → final_node → END
```

节点会自行检查 `selected_agents`，未选中的节点直接跳过。

1. `begin_node` 使用模型将最新请求识别为 `knowledge`、`chat`、`tools` 的一个或多个标签，并用 Pydantic 校验 JSON；格式异常时会尝试修复一次，仍失败则降级为 `chat`。
2. `knowledge_node` 在命中 `knowledge` 时优先检索院内 Qdrant。命中时只允许依据院内片段回答；未命中时调用带 Tavily 工具的联网 Agent，要求其只根据网页片段摘要。
3. `chat_node` 在命中 `chat` 时处理问候、感谢和非医疗闲聊，不处理病情或业务。
4. `final_node` 收集已生成的知识、闲聊和业务回复。只有一个回复时原样输出；多个回复才调用模型合并，失败时确定性拼接。
5. `fastMode=true` 时整张图被替换为 `START → fast_node → summarize_node → END`。`fast_node` 是单个全能 Agent，自己跑工具循环，只挂 `web_search`，最多 3 轮工具调用，超出后会去掉工具再问一次以逼出答案。它没有院内 RAG，也不做意图路由和多节点汇总，因此比正常模式少两轮 LLM 往返，也少一次 Embedding / Qdrant。症状和用药可以联网；本院规定、号源排班请关闭快速模式。

为避免把路由 JSON、工具参数或检索原文泄漏给患者，SSE 只转发根图节点的模型分片，嵌套 Agent（`ns` 非空的子图）分片一律丢弃。单意图时直接流出该节点自身的正文：纯闲聊来自 `chat_node`，纯知识来自 `knowledge_node` 的 RAG 命中分支。多意图请求由 `final_node` 重写正文，只流出 `final_node`。`tool_node` 与知识的 Tavily 兜底走嵌套 Agent，当前不流式，等 `final_node` 透传后一次性下发。快速模式下 token 只来自 `fast_node`。

### 当前功能边界

- `tools` 已接入 LangGraph，并能通过 Java 内部 Tool API 查询启用的科室，作为 Python Tool → Java → MySQL 的只读通信验证。
- 当前尚未接入排班、我的挂号、挂号/取消等业务 Tool；对于这类请求，回复会明确提示当前仅支持科室查询。写操作必须先完成用户确认、MySQL 幂等键、审计和号源事务校验，不能由模型直接发起。
- `memoryEnabled` 已生效。为 `true` 且 `AI_REDIS_URL` 配置可用时，图使用 Redis checkpointer，`conversationId` 作为 `thread_id`，同一会话跨轮共享消息历史与摘要；为 `false` 或 checkpointer 不可用时，退化为单轮无状态图。历史超过 12 条消息后由 `summarize_node` 压缩为摘要，并用 `RemoveMessage` 裁剪旧消息。
- 委托令牌不进入 State，只通过 Runtime Context（`HospitalToolContext`）传递，不会写入 checkpoint。
- 删除会话时，Java 会调用 `DELETE /v1/chat/memory/{conversationId}` 级联清理 checkpoint。
- `patientId` 已传入 State，但现有节点未用它过滤知识库或查询患者业务数据。

扩展业务工具时，应先在 Java 定义经过鉴权和参数校验的受控业务能力，再把对应工具注册到图中；禁止让模型直连数据库或以模型文本直接执行写操作。涉及挂号、取消等写操作时，应使用确认步骤、幂等键和审计日志。

## 5. 知识库维护

### 5.1 支持的文件与处理方式

上传接口支持 `.pdf`、`.docx`、`.txt`、`.md`、`.markdown`：

1. PDF 按页提取文本；扫描版 PDF 没有 OCR，提取不到文本会失败。
2. DOCX 只读取普通段落，不读取表格、图片或嵌入对象。
3. TXT/Markdown 优先按 UTF-8（含 BOM）解码，失败后使用 GB18030。
4. 文本按 800 字符切分、120 字符重叠，使用 Embedding 写入 Qdrant。
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

成功响应包含 `document_id`、`filename` 与 `chunk_count`。建议在导入前对资料进行人工审核，特别是院内地址、楼层、就诊时间和收费说明。

### 5.2 当前管理限制

- 每次上传都会生成新的 `document_id` 和新的向量点，即使文件内容相同也不会自动去重。
- 当前没有按 `document_id` 删除、替换或重建单个文档的 HTTP 接口。
- Python 上传流程不保存原文件，也不写入 MySQL 的 `ai_knowledge_documents` 元数据表；该表目前没有被此流程接入。
- 因此测试或更新资料时应使用独立 collection。生产更新前，应先设计可审计的文档元数据、版本、删除和 Qdrant 清理方案，避免旧资料继续被命中。

## 6. 数据安全与可观测性

- Java 负责浏览器身份认证和会话所有权；Python 仅信任携带共享 `X-Api-Key` 的内部调用。服务间密钥必须足够随机并定期轮换。
- Docker Compose 将 Python 的 8000 端口映射到宿主机。生产环境应限制该端口的网络访问，优先仅允许 Java 网关访问。
- 模型提示词明确禁止诊断、处方、编造院内数据和医疗承诺。急症或明确危险场景要求建议立即急救/急诊，但这不是临床安全体系的替代品。
- Python 中间件为每个请求记录 `request_id`、方法、路径、状态和耗时；日志过滤会脱敏 `Authorization`、`X-Api-Key` 等敏感头。排障时可用 Java 与 Python 的 `X-Request-Id` 关联同一请求。
- 用户消息在发起上游流前落库；收到 `done` 后才保存助手消息。上游中断后可能只保留用户消息，应以 SSE `error` 事件向患者说明重试状态。

## 7. 测试与排障

基础验证命令：

```powershell
cd ai-python
python -m pytest

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
| 资料上传/检索失败 | `QDRANT_URL`、Qdrant 服务状态、Embedding 三项配置、collection 与模型维度是否匹配 |
| 总是走网页或提示知识库不可用 | Qdrant 是否有资料、相似度阈值 `0.8` 是否过高、Tavily 密钥和外网是否可用 |
| 流式答案重复或不完整 | 前端是否为同一轮复用 `clientRequestId`、检查 `done.reply`、用 `X-Request-Id` 对照 Java/Python 日志 |
| “挂号/查排班”没有实际结果 | 这是当前 `tools` 节点未接入的已知限制，不是 Qdrant 故障 |
| 快速模式答不出号源排班或本院楼层/须知 | 这是设计行为，不是故障。快速模式只有闲聊、联网和记忆，请关闭快速模式重问 |

相关实现可从 [`ai-python/README.md`](../ai-python/README.md)、[`aiController.java`](../backend-java/src/main/java/com/wenrun/ai/controller/aiController.java) 和 [`assistant-stream-recovery-highlight.md`](assistant-stream-recovery-highlight.md) 继续阅读。
