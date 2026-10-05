# 温润在线医院

Vue 患者工作台、Spring Boot 业务网关、FastAPI/LangGraph AI 服务及 MySQL/Redis/Chroma。浏览器通过 Java `/api/**` 使用业务与 AI 功能，Java 决定患者权限、执行业务事务并保存消息；Python 负责编排和生成。

## 1Panel 部署

完整步骤见 [1Panel 部署与运行手册](docs/1Panel部署与运行手册.md)。根目录 `compose.yaml` 管理前端 Nginx、Java、Python、MySQL 8.4、Redis 8 五个服务，1Panel OpenResty 接入前端共享网络提供 HTTPS。

先备份已有开发 `.env`，采用 `deploy/.env.example` 配置部署环境。可运行以下命令生成私有配置，填写模型参数并核对面板网络后再放到根目录 `.env`：

```sh
python3 deploy/configure.py --origin https://你的域名 --env .env.deploy
python3 deploy/preflight.py
# preflight 默认读取根 .env；也可 --env .env.deploy 先检查候选配置。
docker compose up -d --build --wait --wait-timeout 300
python3 deploy/smoke.py
```

内部 Java、Python、数据库与 Redis 不发布端口；前端仅发布回环端口 18080，并通过共享网络供 OpenResty 代理。镜像不包含本地 `.env` 或 Java `application.yml`，默认关闭 Agent 正文日志。首次空数据库只导入 `docs/SQL/schema.sql`，不自动装载演示账号。已有数据库按已执行迁移记录升级。

本机未安装 Docker，容器与域名验证应在服务器执行；CI 已加入容器构建、依赖健康等待和只读烟测。Python wheel、Java 打包与源码回归已在本地验证。

## 本地开发

1. 准备 MySQL 和具备 JSON/Search 的 Redis 8。新库导入 `docs/SQL/schema.sql`；已有库先备份，再按日期执行尚未执行的迁移。
2. 将 `ai-python/.env.example` 复制为 `ai-python/.env`，填写模型、Embedding、Redis 及内部调用配置。
3. 将 Java `application.yml.example` 复制为 `application.yml`，填写本地数据库与 Redis；通过启动环境设置服务间共享密钥与 Base64 委托签名密钥，Java/Python 必须一致。
4. 分别在三个终端启动：

```powershell
# AI（8000）
cd ai-python
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --reload

# Java（8080）
cd backend-java
$env:AI_SERVICE_BASE_URL='http://localhost:8000'
$env:AI_SERVICE_API_KEY='与 Python AI_INTERNAL_API_KEY 相同的密钥'
$env:AI_DELEGATION_SIGNING_SECRET='与 Python 完全一致的 Base64 密钥'
mvn spring-boot:run

# 前端（5173）
cd frontend
npm ci
npm run dev
```

开发态 Redis 未配置时可降级为只读问答，关闭需确认的业务写工具。生产部署要求 Redis checkpoint 与权威知识库可用，初始化失败会阻止 Python 启动。

## 验证

```powershell
cd frontend
npm test
npm run lint
npm run build

cd ../backend-java
mvn clean verify

cd ../ai-python
python -m pytest tests -q
python scripts/evaluate_context.py
python -m pip wheel --no-deps . --wheel-dir dist
```

Linux x86_64/Python 3.13 容器使用 `ai-python/requirements.lock`；前端使用 `package-lock.json`。部署脚本测试：`python -m unittest discover -s deploy/tests -q`。

## 当前能力与边界

- 普通模式：级联意图路由、依赖规划、院内 RAG、公开搜索和业务工具；挂号/退号经人工确认，Java 执行事务。
- 快速模式：单个公开搜索 Agent，不使用院内 RAG 和挂号业务工具。
- MySQL 保存会话、消息、结构化摘要及生产 RAG 元数据；Redis 是可丢失的 checkpoint 与 Session/锁存储，Chroma 是可重建索引。
- 摘要收到数据库提交 ACK 后才压缩 checkpoint；恢复使用摘要覆盖位置之后的分页消息。checkpoint 丢失不能恢复历史业务确认。
- 长期偏好功能已删除，健康档案读取、会话摘要和恢复继续保留。
- 定时知识版本的 Worker 激活与失败重试已有回归；真实服务器场景待部署验收。
- 确定性评测不代表真实模型质量；实际 PDF 解析与检索效果仍需代表性资料核对与标注集验证。

## 项目文档

- [技术参考](book/readme.md)
- [项目流程图](docs/流程图.md)
- [1Panel 部署与运行手册](docs/1Panel部署与运行手册.md)
- [简历三大亮点与 Agent 面试准备](docs/简历亮点与Agent面试准备.md)
