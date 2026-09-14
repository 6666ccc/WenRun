# 温润在线医院

项目由 Vue 前端、Spring Boot 业务网关、FastAPI/LangGraph AI 服务和 MySQL 组成。浏览器只访问 `/api/**`，Java 负责登录鉴权、会话归属、消息落库及 AI SSE 转发。

## Docker Compose 启动

1. 将根目录 `.env.example` 复制为 `.env`。
2. 将 `ai-python/.env.example` 复制为 `ai-python/.env`，填写模型与 Qdrant 配置。
3. 保证根目录 `AI_SERVICE_API_KEY` 与 AI 目录 `AI_INTERNAL_API_KEY` 完全一致。
4. 运行 `docker compose up --build`，然后访问 `http://localhost:5173`。

新数据库会由 `docs/SQL/schema.sql` 初始化。已有数据库升级到本轮上下文架构时，应在备份后按顺序执行 `docs/SQL/migrations/2026-09-13-ai-chat-message-metadata.sql`、`2026-09-13-ai-conversation-registry.sql`、`2026-09-13-ai-patient-memory.sql`、`2026-09-13-ai-knowledge-lifecycle.sql`；这些迁移不会因已有 MySQL volume 而自动重跑。

开发 Compose 会启动 Redis 8。Java 登录 Session 使用 db1，Python Agent checkpoint 与会话锁使用 db0（`AI_REDIS_URL`，RediSearch 只能建在 db0）。未配置 `AI_REDIS_URL` 时不保存跨轮 checkpoint，但当前请求仍可使用 Java 从 MySQL 提供的有限消息窗口恢复上下文。

健康助手支持「快速模式」开关。开启后跳过意图路由与回复汇总，由单个挂载了联网检索的 Agent 直接流式作答，并沿用同一会话记忆。快速模式没有院内 RAG，也查不了号源、排班、本人预约和本院楼层/就诊须知；问这些请关闭快速模式。症状和用药可以查公开网页，不能代替面诊。

正常模式采用级联意图路由：高精度规则 → CPU 轻量多标签分类器 → 低置信度时升级 LLM，并带有域外拒识、急症安全短路、分层指标和离线评测集。实现与评测命令见 [`ai-python/README.md`](ai-python/README.md)。

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
python scripts/evaluate_intent_router.py
python scripts/evaluate_context.py
```

主要联调入口为 `POST /api/ai/chat/stream`、`GET /api/ai/conversations` 和 `DELETE /api/ai/conversations/{conversationId}`。删除会话时 Java 会级联清理 Python checkpoint。知识库管理接口支持幂等发布、版本替换、停用、删除和带文件重建。

## 上下文权威边界

- MySQL：会话归属、聊天消息、确认卡片元数据、患者长期偏好与知识文档审计记录的权威存储。
- Redis db0：带 TTL 的 LangGraph checkpoint 与按用户/会话的执行锁；可丢失，不是历史事实源。
- Redis db1：Java 登录 Session；生产配置使用 AOF，不能与 checkpoint 混用数据库编号。
- Qdrant：院内资料的可重建向量索引；检索只接受 `active` 且在有效期内的版本。
- Context Builder：按 token 预算选择结构化摘要、近期消息、最多 5 条长期偏好及外部资料；患者文本、记忆和检索片段均按不可信数据处理。

生产 Redis 使用 `appendonly yes` + `appendfsync everysec`，同时保留周期 RDB，数据目录固定为 `/data/wenrun-redis`。这只解决进程/容器重启恢复，不等同于备份：运维应定期执行 `BGSAVE` 后把该目录快照复制到异机或对象存储，并做恢复演练。checkpoint 本身仍允许丢失；MySQL 才是消息、长期偏好和文档元数据的灾备核心。

## 已知限制

- **长期记忆不是病历。** 仅允许患者明确确认的沟通、预约和无障碍偏好；症状、诊断、药物、剂量和过敏等内容会被服务端拒绝。
- **checkpoint 可丢失。** 默认 TTL 24 小时；超期后从 MySQL 最近消息恢复，恢复窗口以外的信息只能依赖结构化摘要或长期偏好。
- **RAG 安全过滤不是医学事实核验。** 版本、有效期、引用和提示注入扫描能降低风险，但不能证明回答医学正确，仍不能替代面诊。
- **确定性评测不等于真实线上质量。** `context_cases.jsonl` 用于阻断隔离、泄漏和恢复回归；概率型回答质量仍需人工抽检和线上指标。
