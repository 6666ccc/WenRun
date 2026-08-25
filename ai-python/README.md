# 温润诊所 AI 服务

FastAPI 负责运行当前 LangGraph 医院对话工作流，并通过 Java 网关向前端提供同步与 SSE 两种响应。

## 接口

- `GET /health`：存活检查。
- `POST /v1/chat/stream`：SSE 聊天，事件类型为 `status`、`citation`、`token`、`done` 或 `error`。

除 `/health` 外的接口要求请求头 `X-Api-Key`。它必须与 Java 的 `AI_SERVICE_API_KEY` 使用同一值。

## 本地运行

复制 `.env.example` 为 `.env`，填写模型、Embedding、Qdrant 和服务间密钥后运行：

```bash
pip install -e ".[test]"
python -m uvicorn app.main:app --reload
python -m pytest
```

默认监听 `http://localhost:8000`。前端不应直接持有服务间密钥，应始终通过 Java 的 `/api/ai/**` 接口访问。
