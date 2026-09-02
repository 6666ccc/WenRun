# 温润在线医院

项目由 Vue 前端、Spring Boot 业务网关、FastAPI/LangGraph AI 服务和 MySQL 组成。浏览器只访问 `/api/**`，Java 负责登录鉴权、会话归属、消息落库及 AI SSE 转发。

## Docker Compose 启动

1. 将根目录 `.env.example` 复制为 `.env`。
2. 将 `ai-python/.env.example` 复制为 `ai-python/.env`，填写模型与 Qdrant 配置。
3. 保证根目录 `AI_SERVICE_API_KEY` 与 AI 目录 `AI_INTERNAL_API_KEY` 完全一致。
4. 运行 `docker compose up --build`，然后访问 `http://localhost:5173`。

开发 Compose 会启动 Redis 8。Java 登录 Session 使用 db0，Python Agent checkpoint 使用 db1（`AI_REDIS_URL`）。未配置 `AI_REDIS_URL` 时，对话图退化为单轮无状态。

## 本地分别启动

```powershell
# AI（8000）
cd ai-python
python -m uvicorn app.main:app --reload

# Java（8080，先设置与 AI 相同的服务间密钥）
cd backend-java
$env:AI_SERVICE_BASE_URL='http://localhost:8000'
$env:AI_SERVICE_API_KEY='你的服务间密钥'
mvn spring-boot:run

# 前端（5173）
cd frontend
npm install
npm run dev
```

## 验证

```powershell
cd frontend; npm test; npm run build; npm run lint
cd ../backend-java; mvn test
cd ../ai-python; python -m pytest
```

主要联调入口为 `POST /api/ai/chat/stream` 和 `DELETE /api/ai/conversations/{conversationId}`。删除会话时 Java 会级联调用 Python 的 `DELETE /v1/chat/memory/{conversationId}` 清理 checkpoint。

## 已知限制

- **同一会话并发写 checkpoint 未加锁。** Java 侧 `clientRequestId` 只能拦住重复提交的同一条消息；同一 `conversationId` 并发发送两条不同消息时，后写的 checkpoint 会覆盖先写的。前端是单输入框串行发送，实际触发概率低。
- **记忆只是患者自述，不是病历。** 摘要会标注自述来源、禁止新增诊断与药名，但模型仍可能把旧症状当成当前事实。医疗结论仍必须走 RAG 引用或 Tool 返回的真实数据。
- **checkpoint 有 TTL 且可被 LRU 淘汰。** 生产 Redis 是 `allkeys-lru` + 128mb，默认 TTL 24 小时。超期或内存压力下记忆会消失，会话退化为单轮，不报错。MySQL `chat_messages` 仍保留完整消息。
- **摘要会让最后一个 token 到 `done` 事件之间多一次 LLM 调用。** 只在消息超过 12 条时触发。
