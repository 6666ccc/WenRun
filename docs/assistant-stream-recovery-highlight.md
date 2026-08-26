# 健康助手跨页面流式任务恢复与消息幂等

## 项目亮点

针对患者发送问题后 Agent 正在生成答案、患者切换到挂号/缴费等其他页面，再返回聊天页时可能出现请求中断、消息重复和状态错乱的问题，设计并落地了一套跨路由流式任务恢复与请求幂等方案。

该能力让聊天任务不再依赖单个页面组件的生命周期：患者可以自由浏览医院业务页面，返回聊天后仍能看到同一轮对话的正确状态；即使发生重复提交，也不会重复启动 AI 或重复落库。

## 核心实现

### 1. 流式任务脱离聊天页生命周期

将 Assistant 的会话数据、请求状态和 `AbortController` 从 `Assistant.vue` 的局部生命周期提升到应用级运行态。

- 聊天页卸载时不再自动中断生成中的请求；
- 返回聊天页后复用同一份运行态，继续显示流式内容；
- 只有患者主动点击“停止生成”、退出登录或切换账户时才取消任务；
- 对运行中的任务统一维护 `pending`、`streaming`、`completed`、`error`、`stopped` 状态。

相关实现：[useAssistant.js](../frontend/src/composables/useAssistant.js)

### 2. 按请求 ID 精确关联消息

每一轮对话生成独立的 `clientRequestId`，用户消息、助手占位消息、SSE token、完成事件和错误事件都通过该 ID 关联。

这避免了原先“始终更新最后一条助手消息”的隐患，尤其是在路由切换、异步回调延迟或重复请求同时到达时，能够保证内容写入正确的消息。

### 3. Java 网关请求幂等保护

在 Java 网关增加请求级幂等校验：

- 同一用户、会话和 `clientRequestId` 只允许启动一次 AI 上游任务；
- 已完成的重复请求直接返回已保存的助手回复；
- 仍在处理中的重复请求返回 `AI_REQUEST_IN_PROGRESS`；
- 相同请求 ID 对应不同消息时拒绝请求，避免请求 ID 被错误复用。

相关实现：[aiController.java](../backend-java/src/main/java/com/wenrun/ai/controller/aiController.java)

### 4. 数据库唯一约束兜底

`chat_messages` 增加 `client_request_id` 字段，并建立唯一索引：

```text
(user_id, conversation_id, client_request_id, role)
```

即使多个请求并发到达，数据库仍能阻止同一轮 user/assistant 消息重复写入。

迁移脚本：[2026-08-25-ai-message-idempotency.sql](SQL/migrations/2026-08-25-ai-message-idempotency.sql)

## 技术价值

这不是简单的按钮防重复，而是从三个层面共同保证一致性：

```text
页面层：路由切换不丢失流式任务
      ↓
应用层：requestId 精确关联消息状态
      ↓
数据层：唯一索引阻止重复落库
```

因此，即使出现快速切换页面、重复点击、网络重试或 SSE 生命周期抖动，也不会因为单一层面的状态丢失而产生重复消息。

## 验证结果

- 前端 Node 测试：16 项通过；
- 前端 ESLint：通过；
- 前端 Vite 构建：通过；
- Python AI 服务测试：16 项通过；
- Java 改动类：通过本地依赖 `javac` 编译检查；
- MySQL 迁移：已在本地 `wenrun` 数据库执行并确认字段和唯一索引存在。

## 可用于项目介绍的一句话

> 为医疗 AI 助手设计跨页面流式任务恢复机制，将生成任务从页面生命周期中解耦，并结合请求 ID、Java 网关幂等校验和数据库唯一约束，解决了患者切页返回后消息重复、生成状态丢失和重复落库问题。

