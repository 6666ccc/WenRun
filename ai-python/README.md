# AI — FastAPI + LangChain 最简示例

## 安装

```bash
pip install -e .
copy .env.example .env
```

编辑 `.env`，填入 `OPENAI_API_KEY`。

## 运行

```bash
wenrun-api
```

或：

```bash
python -m wenrun_ai.API
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
