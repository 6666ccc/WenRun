# 温润诊所 AI 服务

FastAPI 负责运行当前 LangGraph 医院对话工作流，并通过 Java 网关向前端提供同步与 SSE 两种响应。

## 级联意图路由

正常模式在进入 LangGraph 业务节点前依次执行：

1. 高精度规则：明确挂号/号源、科室目录、院务、寒暄与急症信号；
2. CPU 轻量模型：字符 TF-IDF + One-vs-Rest Logistic Regression；
3. 低置信度、歧义和域外输入升级到原有 LLM 结构化分类；
4. LLM 不可用或结构持续非法时返回确定性澄清，不再默认当作闲聊回答。

训练语料位于 `app/intent/data/training.jsonl`。本地层离线评测：

```bash
python scripts/evaluate_intent_router.py
```

路由会把 `stage`、各标签分数、规则、升级原因、安全信号及模型版本写入
`State.intent_route` 和结构化日志。阈值通过 `INTENT_*` 环境变量配置；调整前应先
扩充独立评测集 `evals/intent_cases.jsonl`，不要直接用训练集选择阈值。

## 接口

- `GET /health`：存活检查。
- `POST /v1/chat/stream`：SSE 聊天，事件类型为 `status`、`citation`、`token`、`done` 或 `error`。
- `POST /v1/chat/documents`：幂等发布 PDF、DOCX、TXT 或 Markdown；可传 `documentId`、`uploadedBy`、`effectiveFrom`、`expiresAt` 和 `forceRebuild`。
- `GET /v1/chat/documents/{document_id}`：查看该文档的所有版本元数据；配置 MySQL registry 时以 MySQL 为准。
- `POST /v1/chat/documents/{document_id}/deactivate`：停止所有 active 版本参与检索。
- `POST /v1/chat/documents/{document_id}/rebuild`：携带新文件重建为下一版本。
- `DELETE /v1/chat/documents/{document_id}`：删除该文档的 Qdrant points，并同步 MySQL 生命周期状态。
- `DELETE /v1/chat/memory/{conversation_id}`：清除单个会话的 Redis checkpoint；需要 `X-Api-Key`，不需要委托令牌。会话归属由 Java 在调用前校验。
- `GET /v1/metrics/intent-routing`：返回当前 Python 进程的规则/轻量模型/LLM/失败分层计数，不包含患者原文；需要 `X-Api-Key`。
- `GET /v1/metrics/context`：返回脱敏的上下文 token、P95 延迟、错误和模式计数。

除 `/health` 外的接口要求请求头 `X-Api-Key`。它必须与 Java 的 `AI_SERVICE_API_KEY` 使用同一值。

## 本地运行

复制 `.env.example` 为 `.env`，填写模型、Embedding、Qdrant 和服务间密钥后运行：

```bash
pip install -e ".[test]"
python -m uvicorn app.main:app --reload
python -m pytest
python scripts/evaluate_intent_router.py
python scripts/evaluate_context.py
```

RAG chunk 必须带 `checksum/version/status/effective_from/expires_at/uploaded_by/updated_at`。生产应配置 `RAG_METADATA_MYSQL_*` 并使用只允许维护 `ai_knowledge_documents` 的数据库账号；MySQL 是生命周期权威源，Qdrant 是可重建索引。检索同时执行 Qdrant 生命周期过滤和 Python 侧 fail-closed 复核；控制字符会被清理，疑似提示注入的 chunk 不进入模型。每轮 context trace 只记录哈希 thread、分区 token 数、记忆/RAG 数量、工具名、延迟与版本，不记录患者原文、密钥或工具结果。

`evaluate_context.py` 的 60 条确定性用例会实际执行 Context Builder、用户作用域 thread、checkpoint 重建、确认映射、RAG 安全过滤和引用格式化，不调用模型。工具选择率是离线代理指标；真实回答质量、首 token 与模型总延迟仍应从线上 context trace 统计。

默认监听 `http://localhost:8000`。前端不应直接持有服务间密钥，应始终通过 Java 的 `/api/ai/**` 接口访问。
