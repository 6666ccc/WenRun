# 健康助手跨页面流式任务恢复与重复消息治理 Implementation Plan

> **For agentic workers:** 按任务顺序实施，每完成一个任务即运行对应测试。未经 Task 1 的证据确认，不直接假设重复消息一定来自自动重发。

**Goal:** 患者发送消息后，即使在 Agent 处理中离开 `/assistant` 再返回，也只能看到一条用户消息；进行中的任务继续显示或以明确状态结束，不能静默恢复成可重复发送状态。

**Architecture:** 将流式请求和会话运行状态从 `Assistant.vue` 的组件生命周期提升到路由之外的应用级 Assistant Store；视图卸载不再自动取消请求，退出登录或显式“停止生成”才取消。每一轮对话使用稳定的 `requestId`，前端依此合并消息，Java 网关依此提供幂等保护。Python AI 服务保持现状，除非证据表明它在单次请求内重复执行。

**Tech Stack:** Vue 3 + Pinia + Vue Router + Fetch/SSE + Spring Boot + MyBatis + MySQL + FastAPI/LangGraph + Node test runner + JUnit 5。

## Global Constraints

- 首先确认真实请求次数，不把截图本身当作“两次 POST”的充分证据。
- 不使用消息文本作为去重键；患者连续发送相同问题可能是合法操作。
- 不把 `AbortController`、`ReadableStream` 等不可序列化对象写入 `localStorage`。
- 不通过简单删除重复气泡掩盖问题；消息必须有稳定 `messageId/requestId` 和明确状态。
- AI 生成期间允许患者访问挂号、缴费、首页等页面。
- “停止生成”、退出登录、账户切换必须真正终止对应请求，不能让旧账户任务继续写入状态。
- Python AI 服务默认不修改；Java 网关继续承担鉴权、会话归属、消息落库及 SSE 转发。
- 保留现有存储键 `wenrun_ai_sessions` 的兼容读取；如升级结构，需要提供归一化迁移和旧数据回退。

## Task 1：建立可重复证据，确定重复发生在哪一层

**Inspect:**

- `frontend/src/views/Assistant.vue`
- `frontend/src/composables/useAssistant.js`
- `frontend/src/api/modules/ai.js`
- `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java`
- `ai-python/app/api/routes/chat.py`

- [ ] 1.1 在浏览器 Network 中开启 Preserve log，清理或新建一个独立测试会话。
- [ ] 1.2 发送一次无敏感信息的测试消息，记录 `conversationId`、请求开始时间和 `/api/ai/chat/stream` POST 数量。
- [ ] 1.3 在收到 `done` 前跳转 `/home`，等待数秒后返回 `/assistant`。
- [ ] 1.4 记录返回后同一会话的消息数组：每条消息的 `id`、`role`、`content`、`meta`；不得只按可见文本判断。
- [ ] 1.5 对照 Java 日志和 `chat_messages`，确认同一会话实际插入了几条 `role=user` 记录、Python 收到了几次调用。

**判定表：**

| 观测结果 | 初步结论 | 后续重点 |
|---|---|---|
| 1 个 POST、前端出现 2 个不同用户消息 ID | 前端状态恢复或事件绑定重复 | Task 2–4，并补充具体触发点测试 |
| 2 个 POST、每个 POST 各有一条用户记录 | 前端重复提交或恢复后重试 | Task 2–5 |
| 1 个 POST、仅 1 条用户消息，但回复丢失 | 纯请求生命周期断裂 | Task 2–4 |
| 1 个 Java POST、Python 收到 2 次调用 | Java 转发/重试问题 | 先定位 Java 调用链，再执行 Task 5 |
| Python 单次调用产生重复 token，但无重复用户消息 | AI/SSE 输出问题 | 单独建立 AI 修复计划，不进入消息去重方案 |

**Exit criteria:** 形成一份简短复现记录，至少包含请求数、前端消息 ID、数据库行数和服务日志关联信息。

## Task 2：用测试固定跨路由期望

**Files:**

- Modify: `frontend/test/ai.test.js`
- Modify: `frontend/test/experience.test.js`
- Create: `frontend/test/assistant-runtime.test.js`
- Create or modify pure helpers under `frontend/src/features/assistant/`

- [ ] 2.1 先写失败测试：同一个 `requestId` 只能创建一条用户消息和一个助手占位消息。
- [ ] 2.2 写失败测试：视图卸载和重新挂载不改变 `pending` 轮次，也不追加用户消息。
- [ ] 2.3 写失败测试：重复的 token/done 事件只能更新与 `requestId` 对应的助手消息，不能更新“最后一条助手消息”。
- [ ] 2.4 写失败测试：用户显式停止后状态变为 `stopped`；普通路由离开不能触发 `stopped`。
- [ ] 2.5 写失败测试：旧版 `wenrun_ai_sessions` 数据缺少 `requestId/status` 时可以正常归一化。
- [ ] 2.6 写失败测试：两个内容相同但 `requestId` 不同的主动发送仍保留为两轮，防止错误文本去重。

**Run:**

```powershell
cd frontend
npm test
```

**Exit criteria:** 新测试在旧实现上至少有一项失败，并准确描述导航中断场景。

## Task 3：将流式运行状态提升到应用级 Store

**Files:**

- Create: `frontend/src/stores/assistant.js`
- Modify: `frontend/src/stores/index.js`
- Refactor: `frontend/src/composables/useAssistant.js`
- Modify: `frontend/src/views/Assistant.vue`
- Modify: `frontend/src/stores/auth.js`

- [ ] 3.1 在 Pinia Assistant Store 中维护 `sessions`、`activeId`、`pendingTurns`、`replyingByConversation` 和任务状态。
- [ ] 3.2 将运行中的 `AbortController` 放在模块私有 registry 中，以 `requestId` 为键；不要放入 Pinia state 或 `localStorage`。
- [ ] 3.3 `sendMessage()` 生成一次稳定的 `requestId`，并同时创建：
  - 一条 `role=user`、`status=pending` 的消息；
  - 一条 `role=assistant`、`status=streaming` 的空占位消息；
  - 两者共享相同 `requestId`。
- [ ] 3.4 将现有 `updateLastAssistant()` 改为按 `requestId` 精确更新，消除“最后一条消息”在并发或恢复时指向错误对象的风险。
- [ ] 3.5 从 `useAssistant()` 删除页面卸载时的 `controller.abort()`；组件卸载只清理视图监听、焦点和计时器。
- [ ] 3.6 `Assistant.vue` 返回时直接订阅 Store：如果任务仍在运行，继续显示流式文本、状态和停止按钮，输入框保持禁用。
- [ ] 3.7 “停止生成”调用 Store 的 `stopRequest(requestId)`；仅该动作将消息标记为 `stopped`。
- [ ] 3.8 `logout()` 和账户切换前调用 `assistantStore.resetRuntime()`：中断全部 controller、停止持久化写入并清空内存中的账户相关状态。
- [ ] 3.9 为当前登录用户隔离运行态。若暂不迁移存储键，至少在载入时校验 owner，避免缓存 Store 跨患者复用。

**Implementation note:** 不建议只在 `App.vue` 外包一层 `<KeepAlive>`。它虽然能避免普通路由卸载，却会引入退出登录后缓存组件和旧请求继续存活的风险；应用级 Store 可以明确管理路由、停止和账户生命周期。

**Run:**

```powershell
cd frontend
npm test
npm run lint
npm run build
```

**Exit criteria:** 路由离开不再取消请求；返回时能看到同一 `requestId` 的原任务状态，且不会新增用户消息。

## Task 4：升级本地会话持久化模型

**Files:**

- Modify: `frontend/src/features/assistant/session.js`
- Modify: `frontend/src/stores/assistant.js`
- Modify: `frontend/test/experience.test.js`
- Modify: `frontend/test/assistant-runtime.test.js`

- [ ] 4.1 消息 `meta` 至少保存 `requestId`、`status`、`createdAt`；可选保存 `completedAt` 和 `errorCode`。
- [ ] 4.2 `normalizeSessions()` 兼容旧消息；旧数据默认为 `status=completed`，不能在刷新后被误判成待恢复请求。
- [ ] 4.3 每次状态变更后以完整、可恢复的会话快照写入 `localStorage`。
- [ ] 4.4 对本次运行中断但无法续接的情况显示明确状态，例如“生成已中断，可重新发送”，而不是静默显示为空闲。
- [ ] 4.5 页面恢复时只展示 Store 中仍存活的运行任务；浏览器整页刷新后不得伪装成仍在流式处理。
- [ ] 4.6 为历史重复数据提供只读兼容，不按文本自动删除既有消息。

**Exit criteria:** 刷新、路由返回、旧数据迁移三种情况下均不会凭空追加消息，且状态对患者可解释。

## Task 5：为 Java 网关增加请求级幂等保护

**Files:**

- Modify: `frontend/src/api/modules/ai.js`
- Modify: `backend-java/src/main/java/com/wenrun/ai/vo/aiRequest.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java`
- Modify: `backend-java/src/main/java/com/wenrun/entity/ChatMessage.java`
- Modify: `backend-java/src/main/java/com/wenrun/repository/ChatMessageRepository.java`
- Modify: `backend-java/src/main/resources/mapper/ChatMessageRepository.xml`
- Create: `docs/SQL/migrations/2026-08-25-ai-message-idempotency.sql`
- Create or modify tests under `backend-java/src/test/java/com/wenrun/ai/`

- [ ] 5.1 前端请求体增加 `requestId`，同一轮的重试必须复用原值，新一轮必须生成新值。
- [ ] 5.2 Java DTO 校验 `requestId` 的长度和格式，并在日志中同时记录 `requestId`、`conversationId`、`userId`。
- [ ] 5.3 数据库为消息保存 `request_id`，建立唯一约束：`(user_id, conversation_id, request_id, role)`。
- [ ] 5.4 保存用户消息由无条件 `INSERT` 改为幂等插入；重复请求不能产生第二条 `role=user` 记录。
- [ ] 5.5 保存助手消息使用相同 `requestId`，重复 `done` 事件不能产生第二条助手记录。
- [ ] 5.6 明确定义“同一 requestId 再次到达”的 HTTP/SSE 行为：
  - 已完成：返回已保存结果；
  - 仍处理中：返回结构化 `AI_REQUEST_IN_PROGRESS`，或订阅现有任务；
  - requestId 相同但请求内容不同：拒绝并记录安全日志。
- [ ] 5.7 不捕获唯一键异常后继续调用 AI；幂等判定必须发生在创建第二个上游任务之前。

**Recommended schema direction:** 如果仅给 `chat_messages` 增加唯一索引无法表达 `processing/completed/failed`，新增 `ai_chat_turns` 表保存轮次状态、请求摘要和最终回复；`chat_messages` 继续作为展示记录。不要用进程内 Map 作为唯一幂等来源，否则多实例和重启后失效。

**Run:**

```powershell
cd backend-java
./mvnw test
```

Windows 环境若项目没有 Maven Wrapper，则使用已安装的 `mvn test`。

**Exit criteria:** 同一用户、会话和 `requestId` 并发提交两次时，最多启动一次 AI 上游任务，数据库最多各有一条 user/assistant 消息。

## Task 6：确认取消链路，但默认不修改 Python AI

**Inspect first:**

- `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java`
- `backend-java/src/main/java/com/wenrun/ai/service/aiService.java`
- `ai-python/app/api/routes/chat.py`

- [ ] 6.1 验证患者点击“停止生成”时，浏览器 fetch 取消、Java `SseEmitter` 完成、Java 上游任务取消和 Python `CancelledError` 日志可以用同一 `requestId` 关联。
- [ ] 6.2 验证普通路由离开不会触发上述取消链。
- [ ] 6.3 如果 Java `Future.cancel(true)` 无法中断阻塞中的 `RestClient` 读取，单独调整 Java HTTP 客户端取消策略；不要把这一问题错误归因于 LangGraph。
- [ ] 6.4 只有当 Task 1 证明 Python 在单次上游请求内重复执行时，才修改 `ai-python` 并增加对应单元测试。

**Run:**

```powershell
cd ai-python
pytest
```

**Exit criteria:** 路由离开、显式停止、网络断开三类事件在日志和产品行为上可以区分。

## Task 7：端到端回归与验收

- [ ] 7.1 正常发送：一条用户消息、一个助手回复、前后端各一轮记录。
- [ ] 7.2 Agent 处理中去首页再返回：仍是一条用户消息，继续显示同一任务，输入框不会错误解锁。
- [ ] 7.3 Agent 处理中去挂号/缴费页再返回：行为与 7.2 相同，不影响业务页操作。
- [ ] 7.4 显式停止后离开再返回：显示已停止状态，不自动恢复、不自动重发。
- [ ] 7.5 快速双击发送按钮或连续按 Enter：同一时刻只创建一轮请求。
- [ ] 7.6 连续主动发送两次相同文本：两轮都保留，且各自 `requestId` 不同。
- [ ] 7.7 断网后恢复：显示可理解的错误状态；重新发送产生新请求，不污染旧助手消息。
- [ ] 7.8 退出患者 A、登录患者 B：B 看不到 A 的会话运行态、消息或仍在生成的结果。
- [ ] 7.9 桌面与移动端分别验证，重点检查移动底栏切换场景。
- [ ] 7.10 运行完整验证：

```powershell
cd frontend
npm test
npm run lint
npm run build

cd ..\backend-java
mvn test

cd ..\ai-python
pytest
```

## Observability Requirements

- Java 每轮至少记录：`requestId`、`conversationId`、`userId`、`state`、是否命中幂等、是否启动上游。
- Python 日志继续记录 `conversation_id`，若 Java 向下传递 `requestId`，再增加该字段用于关联，但不改变模型提示词。
- 前端生产环境不记录患者消息正文；诊断日志只记录 ID、状态和时间。
- 指标建议：进行中任务数、显式取消数、客户端断连数、幂等命中数、重复请求拒绝数、流式失败数。

## Definition of Done

- 一次发送在任何路由切换过程中都只对应一个前端用户消息 ID 和一个后端请求 ID。
- 返回助手页后，进行中、完成、失败、停止四种状态均可准确恢复或解释。
- 路由离开不再等同于取消请求；显式停止和退出登录仍能可靠取消。
- 后端能抵御重复 POST，不能仅依赖前端按钮禁用。
- 自动化测试包含“流式处理中切页再返回”，并通过前端、Java、Python 全量测试。
- 没有通过文本去重误删患者合法的重复提问。

## Out of Scope

- 修改 LangGraph 路由、RAG、提示词或模型选择。
- 将所有聊天历史改造成服务端分页同步系统。
- 多设备实时同步和跨浏览器续接同一条 SSE。
- 对已有重复历史做自动删除或数据库清洗；如确有需要，应另写数据修复脚本并先备份。
