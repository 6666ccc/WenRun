# Smart Healthcare AI 服务

## 安装

```bash
pip install -e ".[test]"
# PowerShell
Copy-Item ../.env.example .env
# macOS/Linux
cp ../.env.example .env
```

编辑 `.env`，填入 DashScope 与内部 API 相关配置。

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
curl -X POST http://localhost:8000/v1/chat -H "Content-Type: application/json" -d "{\"message\":\"你好\"}"
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
