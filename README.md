# 温润在线医院

项目由 Vue 前端、Spring Boot 业务网关、FastAPI/LangGraph AI 服务和 MySQL 组成。浏览器只访问 `/api/**`，Java 负责登录鉴权、会话归属、消息落库及 AI SSE 转发。

## Docker Compose 启动

1. 将根目录 `.env.example` 复制为 `.env`。
2. 将 `ai-python/.env.example` 复制为 `ai-python/.env`，填写模型与 Qdrant 配置。
3. 保证根目录 `AI_SERVICE_API_KEY` 与 AI 目录 `AI_INTERNAL_API_KEY` 完全一致。
4. 运行 `docker compose up --build`，然后访问 `http://localhost:5173`。

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

主要联调入口为 `POST /api/ai/chat/stream` 和 `DELETE /api/ai/conversations/{conversationId}`。
