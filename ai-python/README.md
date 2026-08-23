# 温润诊所 AI 服务骨架

该目录只保留 FastAPI 服务骨架，未实现任何聊天、模型、记忆、Agent、Tool、RAG、向量数据库或 SQLite 能力。

## 保留的接口

- `GET /health`：服务存活检查。
- `POST /v1/chat`、`POST /v1/chat/stream`、`POST /v1/chat/resume/stream`：保留既有路径和请求校验，但会返回 `501 Not Implemented`，避免调用方误以为 AI 能力已可用。

聊天接口仍要求 `X-Api-Key`，其值来自 `AI_INTERNAL_API_KEY` 或 `AI_SERVICE_API_KEY`。

## 运行

```bash
pip install -e ".[test]"
python -m uvicorn app.main:app --reload
python -m pytest
```

后续实现请从 `app/api/routes/chat.py` 的占位接口开始，并按需要自行接入模型、会话、工具和知识库。
