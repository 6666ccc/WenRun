# Smart Healthcare AI 服务

## 安装

```bash
pip install -e ".[test]"
# PowerShell
Copy-Item ../.env.example .env
# macOS/Linux
cp ../.env.example .env
```

编辑 `.env`，填入模型厂商 API Key 与 Java ↔ Python 服务间共享 Key：

```dotenv
DASHSCOPE_API_KEY=你的模型厂商APIKey
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_CHAT_MODEL=qwen-plus
EMBEDDING_MODEL=text-embedding-v3
AI_INTERNAL_API_KEY=与 Java 的 AI_SERVICE_API_KEY 保持一致
AI_JAVA_BASE_URL=http://localhost:8080
```

其中 `DASHSCOPE_API_KEY` 只在 Python 进程使用；`AI_INTERNAL_API_KEY` 只用于 Java 调 Python 的 `X-Api-Key` 鉴权。正式 Key 变更时只需更新环境变量并重启对应服务。

## 运行

```bash
python -m uvicorn app.main:app --reload
```

## 验证

```bash
python -m pytest
```

## 调用

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${AI_INTERNAL_API_KEY}" \
  -d '{"message":"你好","conversationId":"demo-1","memoryEnabled":true}'
```

## 目录

```text
ai-python/
├── app/
│   ├── api/routes/
│   ├── api/dependencies/
│   ├── core/
│   ├── models/
│   ├── graphs/hospital/
│   ├── rag/
│   ├── services/
│   └── utils/
├── langgraph.json
├── pyproject.toml
└── requirements.txt
```
