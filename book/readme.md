# 温润在线医院 · 技术参考

核对日期：2026-10-04。按当前工作区源码整理，启动步骤见[项目 README](../README.md)，业务与 AI 流程见[流程图](../docs/流程图.md)。源码存在不等于完成生产验收。

## 架构与权威边界

| 模块 | 职责 | 主要入口 |
| --- | --- | --- |
| Vue | 患者工作台、健康档案、挂号、SSE、来源与确认卡片 | `frontend/src/composables/useAssistant.js` |
| Spring Boot | 登录、患者授权、业务事务、消息与摘要落库、AI 网关 | `backend-java/src/main/java/com/wenrun/ai/service/aiService.java` |
| FastAPI / LangGraph | 路由、规划、知识问答、业务工具、上下文压缩与恢复 | `ai-python/app/graphs/hospital/graphs.py` |

浏览器只访问 Java `/api/**`。Java 校验账号与患者权限，向 Python 签发短期委托 JWT；Python 调业务工具时仍由 Java 检查权限并执行事务。模型不能靠生成文字改变业务状态。

MySQL 是业务、消息、会话摘要和生产 RAG 元数据的权威存储。Redis db0 保存可丢失的 Python checkpoint，db1 用于 Java Session 与会话锁。Chroma 是可重建的向量索引，不承担发布与授权的最终判定。

## 编排与业务工具

普通模式先执行 `compact_node`，再走高精度规则、Jev 或 Ollama、必要时云端 LLM 的级联意图路由。单意图直达；多意图由 `plan_node` 拆分子目标与依赖，无依赖分支可并行，知识结论可接力业务节点。`final_node` 使用 `defer=True` 等待分支完成。

快速模式同样先压缩上下文，然后走单个公开搜索 Agent；不使用院内 RAG 或挂号业务工具。

挂号与取消挂号写工具在普通模式、有 checkpoint、运行时允许写入时才可见。工具先查询 Java 权威业务信息，再用 `interrupt()` 展示确认卡片；批准后才写入。挂号幂等键由会话 ID 与 `tool_call_id` 构成，Java 事务负责实际号源与重复提交校验。

恢复校验当前中断与 `interruptId`，过期或冲突卡片不执行；不能从数据库里的历史卡片重建写操作。挂起期间的其他问题走关闭写能力的旁路图。

入口：`ai-python/app/graphs/hospital/confirmation.py`、`ai-python/app/graphs/hospital/tools/registration_write.py`、`backend-java/src/main/java/com/wenrun/ai/security/DelegationTokenService.java`、`backend-java/src/main/java/com/wenrun/service/impl/RegistrationServiceImpl.java`。

## 上下文、摘要与恢复

Context Builder 按用途选择摘要、近期消息、外部资料，系统规则与不可信文本分开处理。患者自述标为 `unverified`，工具结果必须实时获取，摘要不授予权限，也不是业务台账。

默认总输入估算预算为 8000 tokens。`BudgetedChatModel` 在模型生成边界重新组装输入，包含工具 schema；上下文超限时缩减预算，仅重试失败的单次模型调用，最多两次重试，不重跑工具或整张图。流式输出已有内容或工具片段后不重试。估算不等于供应商精确 tokenizer。

结构化摘要包含 `schema_version=2`、患者自述及其数据库消息来源、未解决事项、失效项、版本和连续覆盖位置。候选摘要经 Java 校验执行锁归属、来源与版本后写入 MySQL；收到 ACK 后才从 checkpoint 移除覆盖消息。提交失败保留原文，冲突要求恢复。

checkpoint 丢失时使用数据库摘要和其覆盖位置之后的分页消息恢复，并受恢复时间与输入预算限制。执行中断丢失后仍不能重建业务写入。长期偏好管理、跨会话偏好存储和注入已移除，必要健康档案读取继续保留。

入口：`ai-python/app/graphs/hospital/context_builder.py`、`ai-python/app/models/budgeted.py`、`ai-python/app/graphs/hospital/nodes/summarize.py`、`ai-python/app/graphs/hospital/rehydration.py`、`backend-java/src/main/java/com/wenrun/ai/service/AiConversationMemoryService.java`。

## RAG 生命周期与检索

离线链路为上传、异步解析、清洗、结构化切分、质量报告、审核和显式发布。逻辑文档、版本、构建、任务、原文件与解析产物分开登记。Worker 使用任务租约和 fence 阻止失效任务提交。

发布先将向量写为 `pending`，再提交权威发布登记，最后切换向量可见性。登记失败尝试补偿删除；登记已提交而索引切换失败时，重复发布可修复可见状态。这是补偿与重试机制，不是跨存储原子事务。

检索先过滤向量状态与有效时间，再核对发布登记、版本、访问范围和文本安全。来源保留文档、版本、构建、片段及页码或章节定位；原文件读取走鉴权接口。

解析支持 PDF / DOCX，具备表格切分、OMML 公式转换、结构与质量告警。复杂 PDF 阅读顺序、公式和表格仍有样本限制，见[历史解析验收](../docs/RAG解析切分验收评估-2026-09-30.md)。

`rag/evaluation.py` 提供 Recall@k、Precision@k、Hit Rate@k、MRR、nDCG@k。当前没有真实医院问答标注集，不能宣称线上召回或医学回答正确率提升。Worker 每 30 秒检查到期 scheduled 版本，成功切换索引后提交 active 状态；失败保留可重试记录，已覆盖到期、索引失败重试与旧版本替换回归，服务器定时发布仍需部署验收。

入口：`ai-python/app/rag/ingestion/service.py`、`ai-python/app/rag/lifecycle.py`、`ai-python/app/rag/lifecycle_repository.py`、`ai-python/app/rag/chroma.py`、`ai-python/app/rag/safety.py`、`ai-python/app/rag/evaluation.py`。

## 验证与证据

测试覆盖工具确认、业务幂等、患者隔离、预算、摘要提交、分页恢复、RAG 生命周期和检索指标。确定性上下文门禁配置在 `.github/workflows/context-safety.yml`，评测入口为 `ai-python/scripts/evaluate_context.py`。

[长期偏好移除验收](../docs/长期偏好功能移除-验收.md)与[确定性评测 JSON](../docs/context-without-preferences-evaluation.json)为此前运行记录；本次文档整理未重跑业务测试。合成用例通过不代表真实模型回答质量或生产 SLA。

简历表述与面试追问见[三大亮点](../docs/简历亮点与Agent面试准备.md)。

容器构建、1Panel 反向代理、健康检查、升级与备份恢复见[部署与运行手册](../docs/1Panel部署与运行手册.md)。
