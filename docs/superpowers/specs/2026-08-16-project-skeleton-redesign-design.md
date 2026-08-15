# 项目骨架重设设计

日期：2026-08-16  
范围：只做目录/包名/import 的机械搬家。不补功能、不改业务逻辑、不把未写完的模块「写好」。

## 0. 硬约束：不改内容

本次是骨架重构，不是功能迭代。实施时只允许下面几类改动：

1. `git mv` 与空目录占位（缺的骨架文件夹用 `__init__.py` 或 `.gitkeep`，里面不写实现）。
2. 因搬家必须改的 `package` / `import` / XML `namespace` / `@MapperScan` / 日志前缀 / `pom` 坐标。
3. 前端 Pinia：把现有 `auth` 等价迁到 `defineStore`，不增加字段、不增加 store、不改页面逻辑。
4. 根级新增编排文件：`docker-compose.yml`、`.env.example`、各端 Dockerfile（只包装现有启动方式）。

明确禁止：

- 补写 AI：不填空的 `rag.py`、不新增 knowledge 路由、不新增 `/health`（若现在没有）、不把 LLM/Qdrant 改成工厂、不写 `core/llm.py` 实现、不写 `services/` 业务、不改节点/图拓扑/prompt。
- 不「修好」`pyproject.toml` 里尚未存在的 `wenrun_ai` 包；只改与新路径冲突的字段，缺的入口留给作者手写。
- 不改 `application.yml` 里已有的密码/api-key 写法（只改包名相关配置项）。
- 不改 Java/Python 异常处理策略，不改 API 契约，不改页面 UI。
- 不把未完成代码补全到可生产；空文件保持空。

## 1. 目标与约束

把现有三端（误名为 `React/` 的 Vue 3 前端、`WenRun/` Spring Boot、`AI/` FastAPI）重排为参考骨架，并补上根级 `docker-compose.yml`、`.env.example`、`docs/`。

已锁定决策：

| 项 | 选择 |
|----|------|
| 落地方式 | 原地 `git mv` + 机械重构，不空目录重建 |
| Java 包名 | `com.wenrun` |
| Docker 服务 | frontend、backend-java、ai-python、mysql、qdrant |
| Java 数据访问 | `mapper/` → `repository/`，技术仍为 MyBatis，类名 `XxxRepository` |
| AI 服务 | FastAPI 交付 + LangGraph 编排 + LangChain 模型/工具/检索 |
| 前端状态 | 引入 Pinia，`store/` → `stores/` |
| Java AI 包 | 保留 `com.wenrun.ai` 作为薄网关，LangChain 不进 Java |

成功标准：目录与参考骨架对齐；旧路径/旧包名引用清掉；现有测试在搬家后仍能跑（不为此补新测试逻辑）；登录、挂号等业务 API 路径不变；现有 `POST /v1/chat` 仍挂在原路径。不要求 AI 模块比现在「更能跑」。

## 2. 目标目录树

```text
Online hospitals/
├── docker-compose.yml
├── .env.example
├── frontend/                      # 原 React/
│   └── src/
│       ├── api/
│       ├── components/
│       ├── views/
│       ├── stores/                # Pinia
│       ├── utils/
│       ├── router/
│       ├── composables/
│       └── features/
├── backend-java/                  # 原 WenRun/
│   ├── src/main/java/com/wenrun/
│   ├── src/main/resources/mapper/
│   ├── src/test/
│   └── pom.xml
├── ai-python/                     # 原 AI/
│   ├── app/
│   ├── langgraph.json
│   ├── pyproject.toml
│   └── requirements.txt
└── docs/
    ├── SQL/
    └── superpowers/
```

路径对照：

| 现在 | 之后 |
|------|------|
| `React/` | `frontend/` |
| `WenRun/` | `backend-java/` |
| `AI/` | `ai-python/` |
| `com.example.wenrun` | `com.wenrun` |
| `.../mapper/XxxMapper.java` | `.../repository/XxxRepository.java` |
| `React/src/store/` | `frontend/src/stores/` |
| `AI/app/router/`、`schemas/`、`agent/` | 见第 6 节 |
| `WenRun/docs/SQL/` | `docs/SQL/` |
| 根目录 `sql.sql` | 归档为 `docs/SQL/legacy-export.sql`，不以它为权威 |

保留但骨架未画出的目录：前端 `router/`、`composables/`、`features/`；Java `entity/`、`dto/`、`vo/`、`common/`、`ai/`。

## 3. Docker、环境变量、端口

`docker-compose.yml` 编排五个服务，同一网络，用服务名互访。

| 服务 | 宿主机端口 | 容器内互访 |
|------|------------|------------|
| frontend | 5173 | 浏览器入口；开发时 `/api` 代理到 backend-java:8080 |
| backend-java | 8080 | `jdbc:mysql://mysql:3306/wenrun`；`http://ai-python:8000` |
| ai-python | 8000 | `http://qdrant:6333` |
| mysql | 3306 | 库名 `wenrun` |
| qdrant | 6333 HTTP、6334 gRPC | 向量库 |

依赖顺序：mysql 与 qdrant healthcheck 通过后启动 backend-java 与 ai-python，再启动 frontend。MySQL 首次初始化挂载 `docs/SQL/schema.sql` 与 `docs/SQL/seed.sql`。

根目录 `.env.example` 是唯一模板，不提交真实密钥。至少包含：

- 前端：`VITE_API_BASE_URL`（开发可空，走 Vite 代理）
- Java：数据源 URL/用户/密码、JWT、`AI_SERVICE_BASE_URL`、`AI_SERVICE_API_KEY`
- Python：`QDRANT_URL`、`QDRANT_COLLECTION`、`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`DASHSCOPE_CHAT_MODEL`、`EMBEDDING_MODEL`、对内 API Key
- MySQL：`MYSQL_DATABASE=wenrun`、`MYSQL_ROOT_PASSWORD`

`.env.example` 只列出变量名与本地默认端口，不改现有 `application.yml` 里已经写死的密码/api-key（那是内容变更，留给后续）。本地不跑 Docker 时端口保持 `localhost:8080 / 8000 / 3306 / 6333`。各子项目 Dockerfile 只包装现有启动命令，不新增构建逻辑。

## 4. Java 分层（`backend-java`）

根包 `com.wenrun`，启动类仍为 `WenRunApplication`。`pom.xml`：`groupId` 为 `com.wenrun`，`artifactId` 为 `backend-java`。

```text
com.wenrun
├── WenRunApplication.java
├── controller/          # HIS 业务控制器
├── service/ + impl/ + support/
├── repository/          # 原 mapper，MyBatis 接口，类名 XxxRepository
├── config/
├── util/                # JwtUtil + 原 common.util.BizNoUtil
├── entity/ dto/ vo/
├── common/              # Result、异常、上下文、常量（不含 util）
└── ai/                  # 薄网关，不承载 LangChain
    ├── controller/
    ├── service/
    ├── config/
    ├── client/
    ├── dto/ vo/ exception/
    └── knowledge/       # 知识库元数据管理（上传、状态、调 Python 入库）
```

数据访问：

- `@MapperScan("com.wenrun.repository")` 只扫一个包。
- 原 `ai.knowledge.mapper.AiKnowledgeDocumentMapper` 迁到 `com.wenrun.repository.AiKnowledgeDocumentRepository`。
- XML 仍在 `src/main/resources/mapper/`，文件名改为 `XxxRepository.xml`，namespace 同步。
- `type-aliases-package` 与日志前缀改为 `com.wenrun`。

`com.wenrun.ai` 保持现有文件与职责，只改包名与 import；不新增网关能力，不在 Java 中编排 Agent。知识库 mapper 随统一 `repository/` 搬家，类体不改。

对外 HTTP 路径不变。测试包同步改名；Mockito 类型从 `XxxMapper` 改为 `XxxRepository`，断言与用例逻辑不动。

## 5. 请求数据流

```text
浏览器 → frontend (Vite 5173, /api 代理)
      → backend-java :8080
            ├─ HIS 业务 → MySQL
            └─ /api/ai/* → com.wenrun.ai 网关
                         → ai-python :8000
                              → LangGraph
                              → LLM / Tools / Retriever
                              → Qdrant :6333
```

聊天兼容路径：Java 继续调用 FastAPI `POST /v1/chat` 与 `POST /v1/chat/stream`。知识库继续 `POST /v1/knowledge/ingest` 与 delete 路径。

## 6. AI 服务（`ai-python`）：只搬目录，对齐官方分层空位

目标分层给后续手写预留位置，**现有代码原样挪过去**。缺的层建空包，不把图、RAG、入库「补完」。

```text
ai-python/app/
├── main.py                      # 现有文件，只改 import
├── api/routes/                  # 现有 router/chat.py 挪入
├── api/dependencies/            # 空包，留给手写
├── core/                        # 空包，留给手写配置/LLM 工厂
├── models/                      # 原 schemas，文件内容不动
├── graphs/hospital/
│   ├── state.py                 # 原 states.py
│   ├── graph.py                 # 原 workflow.py
│   ├── nodes/                   # 原 nodes，内容不动
│   ├── tools/                   # 原 tools，内容不动
│   └── prompts/                 # 空包，留给手写
├── rag/                         # 原 RAG/rag.py（可为空）+ memory/qdrant.py
├── services/                    # 空包，留给手写
└── utils/                       # 空包，留给手写
```

现有文件落点：

| 现在 | 之后 |
|------|------|
| `app/router/chat.py` | `app/api/routes/chat.py` |
| `app/schemas/` | `app/models/` |
| `app/agent/graph/workflow.py` | `app/graphs/hospital/graph.py` |
| `app/agent/graph/states.py` | `app/graphs/hospital/state.py` |
| `app/agent/graph/nodes/` | `app/graphs/hospital/nodes/` |
| `app/agent/tools/` | `app/graphs/hospital/tools/` |
| `app/agent/RAG/rag.py` | `app/rag/rag.py`（保持空） |
| `app/agent/memory/qdrant.py` | `app/rag/qdrant.py` |

约束：

1. 节点里现有的「import 时创建 ChatOpenAI / Qdrant」保持原样，不抽工厂。
2. 不新增 chat/stream、knowledge ingest、health 等现有代码没有的路由。
3. `pyproject.toml` / `requirements.txt` / `README.md` 只改路径表述；不补 `wenrun_ai` 包、不重写依赖、不实现 CLI。
4. `langgraph.json` 若添加，只指向搬家后的 graph 模块路径，不新增 graph 代码。
5. 现有对外路径（如 `POST /v1/chat`）随文件搬家保留，不扩展。

## 7. 前端（`frontend`）

技术栈仍为 Vue 3 + Vue Router + Vite，仅目录改名并引入 Pinia。

- `main.js` 注册 `createPinia()`。
- `stores/auth.js` 用 `defineStore('auth', …)` 替换手写 `reactive`；继续导出 `useAuth`。
- 调用方 import 从 `../store` 改为 `../stores`。
- `localStorage` key 仍为 `wenrun_user`、`wenrun_token`；login/logout 字段不变。
- 本次不新增第二个 store；助手状态留在 `composables` / `features`。
- `api/`、`components/`、`views/`、`utils/` 保持现有职责。

## 8. 文档与 SQL

权威建库脚本：`docs/SQL/schema.sql`（来自现 `WenRun/docs/SQL/schema.sql`，含库名与注释）。  
种子数据：`docs/SQL/seed.sql`。  
根目录 `sql.sql` 为工具导出且注释乱码，归档为 `docs/SQL/legacy-export.sql` 后从根目录移除，避免双源。

设计与计划文档放在 `docs/superpowers/`。

## 9. 错误处理

不新增、不改写错误处理。现有 Java `GlobalExceptionHandler` / `AiExceptionHandler` 只改包名。Python、前端保持搬家前的行为。Compose 仅声明依赖与 healthcheck，不改应用内重试策略。

## 10. 验证

只验证「搬家没有把现有能力弄坏」，不验证新写的 AI 能力：

1. 目录树与第 2、6 节一致；工作区不再使用 `React/`、`WenRun/`、`AI/`、`com.example.wenrun`。
2. `backend-java`：现有 `mvn test` 通过。
3. `frontend`：`npm run build` 通过；页面仍从 `stores` 取 auth。
4. `ai-python`：现有 `main.py` 与 chat 路由在更新 import 后仍能加载；不要求补健康检查或 RAG。
5. 存在 `.env.example` 与可解析的 `docker-compose.yml`。
6. 空的 AI 文件（如 `rag.py`）搬家后仍为空。

## 11. 非目标

- 不补写、不重构、不「完成」AI 模块；作者将自己手敲。
- 不改页面 UI、不改业务 API 契约、不重写 Agent 意图拓扑与节点内部实现。
- 不引入 Spring Data JPA；MyBatis 只改目录与类名。
- 不把前端改成 React；不把助手会话迁入 Pinia。
- 不接入 LangSmith / LangGraph Platform；不把 LLM 调用改成官方最佳实践实现。
- 不提交真实 `.env` 或密钥。

## 12. 建议实施顺序

1. 顶层 `git mv`（React/WenRun/AI → frontend/backend-java/ai-python）并归并 docs/SQL。
2. Java 包名 + repository 重命名 + yml/pom 修改，跑测试。
3. 前端 Pinia 与 import 修改，跑 build。
4. Python 按第 6 节搬家并改 import；空包占位；不补实现。
5. 根级 `.env.example`、Dockerfile、`docker-compose.yml`。
6. 全库检索旧路径/旧包名，按第 10 节验证。
