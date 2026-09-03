# 秋招冲刺 TODO

> 目标：把项目做到「可写进 2027 秋招简历、可现场演示、经得起追代码」。
> 定位：Java 后端 / AI 应用开发 / AI 全栈。不作为纯算法岗主项目。
> 当前综合：**7.6 / 10**。会话记忆与快速模式已落地；面试最大风险仍是文档过时、公网 HTTP、仓库与线上不完全同构。完成剩余 P0 + 前三项 P1 后，可作为简历第一项目。

线上 Demo：`http://47.100.11.196/home`（目前仍是裸 IP + HTTP）。

建议顺序：**先修文档真实性 → HTTPS → 对齐 Docker / 锁版本与 CI → 补 E2E、压测与 AI Eval → 最后做 HITL 写操作**。

---

## 近期已落地（不要再当成待办）

- [x] LangGraph Redis checkpoint：`conversationId` 作为 `thread_id`，Shallow saver + TTL；委托令牌只走 `HospitalToolContext`，不进 State
- [x] 删除会话时 Java 级联调用 `DELETE /v1/chat/memory/{conversationId}` 清理 checkpoint
- [x] Java 登录 Session 可走 Redis db1（`WENRUN_AUTH_SESSION_STORE=redis`），不再只有单机内存 Token
- [x] 只读业务 Tool：科室、医生、排班、本人挂号（写操作仍不在 Agent 上）
- [x] 健康助手「快速模式」：`fast_graph = START → fast_node → summarize_node → END`，只挂 Tavily 联网 + 会话记忆，不挂院内 RAG；与正常模式共用同一 `thread_id`
- [x] 开发 Compose 已加入 Redis 8；Java Session 用 db1，Python checkpoint 用 db0
- [x] 根 README 已写 Docker 启动、已知限制（并发写 checkpoint、摘要拖尾、TTL/LRU）和快速模式边界

---

## 0. 立即处理（安全收尾）

- [ ] 更换或重置已在聊天/HTTP 登录中暴露的 Demo 账户密码，改为专用演示账号
- [ ] 确认线上 `.env`、服务间密钥、委托 JWT 签名密钥未写入仓库
- [ ] 在 README / 演示说明中写清：当前 Token 仍是 `localStorage` Bearer，公网 HTTP 环境不安全

---

## P0-1 修正文档与代码不一致（最危险）

面试官一旦对代码，夸大或过时表述会直接扣分。原则：**要么实现，要么立刻删掉相关说法**。

骨架文档 [`docs/项目流程骨架.md`](docs/项目流程骨架.md) 大体已对齐代码；其余文档仍有旧口径。

### 删掉或改写过时表述

- [ ] 修订 [`docs/求职项目评估与流程图.md`](docs/求职项目评估与流程图.md)
  - [ ] 推荐表述里的「人工确认」——当前 AI 只能查询号源，不能执行挂号；HITL 尚未做
  - [ ] 「适合挂号这种固定步骤加人工确认的流程」——当前图是固定顺序多意图，不是 interrupt 挂号
  - [ ] 「登录态仍是单机内存 Token」——代码已支持 Redis Session，文档还在写旧方案
  - [ ] 「通过包装 saver 避免令牌被持久化」——现实现是 Runtime Context，不是包装 saver
  - [ ] 更正测试数量：文档写 Java 61、Python 83；源码统计为前端 16、Java 43、Python 88（本机缺 Maven，Java 未复跑）
  - [ ] 补上已实现能力：Redis Session、checkpoint、快速模式、四类只读 Tool
- [ ] 修订 [`docs/AI模块开发与运维指南.md`](docs/AI模块开发与运维指南.md)
  - [ ] 第 4 节图示仍写 `begin → knowledge → chat → final`，缺 `tool_node` / `summarize_node`
  - [ ] 「尚未接入排班、我的挂号」已过时；排障表「挂号/查排班没有实际结果」会误导（正常模式已有只读 Tool，快速模式才查不了）
  - [ ] 聊天请求 JSON 示例补 `fastMode`
- [ ] 修订根目录 [`README.md`](README.md)：补能力边界、演示账号、已知限制入口；不要再写「当前图没有 checkpointer」
- [ ] 全文检索「人工确认 / interrupt / 单机内存 / 没有 checkpointer / 尚未接入排班」并逐条核对代码

### 同步事实口径

- [ ] 在面试稿 / README 中写死：
  - 正常模式：查询号源 + RAG + SSE + 会话记忆
  - 快速模式：跳过路由，闲聊 + 联网 + 记忆，**没有院内 RAG，查不了号源排班和本院规定**
  - 都不是「可执行挂号 Agent」
- [ ] 本机补齐 Maven（或加 Maven Wrapper），复跑 `mvn test`，把三端测试数量写进文档并保持更新

**完成标准：** 任意文档里出现的能力，都能在对应源码里指到实现；指不到的一律删除。

---

## P0-2 配置域名和 HTTPS

线上目前只有裸 IP + HTTP，443 不可用。登录密码和 `localStorage` Bearer Token 都走明文，见 [`frontend/src/api/request.js`](frontend/src/api/request.js)。

- [ ] 绑定域名，申请 TLS 证书（Let's Encrypt 即可）
- [ ] HTTP 强制跳转 HTTPS；关闭公网明文 80 业务入口（可只留跳转）
- [ ] Nginx 响应头：
  - [ ] `Content-Security-Policy`
  - [ ] `X-Content-Type-Options: nosniff`
  - [ ] `Referrer-Policy`
  - [ ] 点击劫持防护（`X-Frame-Options` / `frame-ancestors`）
- [ ] 隐藏 Nginx 具体版本（`server_tokens off`）
- [ ] 登录接口限流
- [ ] Token 方案二选一，并在文档写死：
  - [ ] 推荐：Secure + HttpOnly Cookie
  - [ ] 或明确保留 `localStorage` Bearer，并标注「仅演示，不适合公网 HTTP」
- [ ] 部署后用浏览器验证：证书有效、密码不再走明文、首页 / 登录 / 健康助手可访问

**完成标准：** 演示链接是 `https://域名/...`，登录链路不再走裸 HTTP。

---

## P0-3 让仓库真正能复现线上部署

已完成：开发 Compose 有 Redis；生产 Compose 文件已在仓库（[`docker-compose.prod.yml`](docker-compose.prod.yml)）。

仍不一致：

- [`frontend/Dockerfile`](frontend/Dockerfile) 启动的是 Vite 开发服务器（5173）
- 开发 Compose 没有 Qdrant（Python RAG 仍依赖宿主机或 `host.docker.internal`）
- Python 依赖未锁版本（[`ai-python/pyproject.toml`](ai-python/pyproject.toml)）
- 生产镜像仍使用 `mysql:latest`、`qdrant/qdrant:latest`

### 镜像与生产对齐

- [ ] 前端改为多阶段镜像：Node 构建 + Nginx 运行静态资源，不再在生产跑 Vite
- [ ] 生产 Compose 的前端端口、反向代理与真实线上一致
- [ ] 固定 MySQL / Qdrant / Redis / Node 镜像版本，禁止业务依赖 `latest`

### 一条命令启动开发环境

- [x] [`docker-compose.yml`](docker-compose.yml) 加入 Redis，Java / Python 默认连 `redis` 主机名
- [ ] 开发 Compose 加入 Qdrant，并改掉 `ai-python/.env.example` 里的 `host.docker.internal`
- [ ] 验证：`docker compose up --build` 后可打开前端、登录、走通健康助手查询号源（含快速模式开关）

### 可复现构建

- [ ] Java 增加 Maven Wrapper（`mvnw` / `mvnw.cmd`），本机无全局 Maven 也能测
- [ ] 前端 Dockerfile / CI 使用 `npm ci`，不用 `npm install`
- [ ] Python 增加 `uv.lock`（或等价锁文件），依赖全部钉版本
- [ ] 更新 README：开发 / 生产两套启动步骤、必填环境变量、健康检查入口

**完成标准：** 新克隆仓库 + `.env`，一条命令能拉起与线上同构的演示环境。

---

## P1-1 GitHub Actions CI

- [ ] 三端测试：前端 / Java / Python
- [ ] Lint + 前端构建
- [ ] Docker 镜像构建（至少前端多阶段、Java、Python）
- [ ] 基础安全扫描（依赖漏洞即可，不必上完整商业方案）
- [ ] README 状态徽章（build / test）
- [ ] CI 使用 Maven Wrapper、`npm ci`、锁定的 Python 依赖

**完成标准：** 主分支每次推送都有绿勾；面试时可点开 Actions。

---

## P1-2 真实 E2E

- [ ] 用 Testcontainers 或 Compose 拉起 MySQL、Redis、Qdrant、Java、Python
- [ ] Playwright（或同类）跑通：登录 → 查询号源 → 查看挂号
- [ ] 覆盖空状态、未登录拦截、健康助手查询内科当天号源
- [ ] 覆盖快速模式：开启后问号源应拒绝编造并引导关闭；关闭后能查到排班
- [ ] CI 中可重复执行，失败日志可定位到服务

**完成标准：** 一条 CI job 证明「不是静态页面，全链路可回归」。

---

## P1-3 AI Eval（Agent 岗辨识度）

准备 50–100 条固定问题，至少统计：

- [ ] 意图正确率（正常模式）
- [ ] Tool 成功率（含「当天内科号源」这类已验证场景）
- [ ] RAG 命中率、引用覆盖率
- [ ] 首 Token 延迟、P95 延迟；**对比快速模式 vs 正常模式**
- [ ] 单次 / 批量 Token 成本
- [ ] 把评测脚本、数据集、最新报告放进仓库（例如 `docs/eval/`）
- [ ] README 用一张表展示最新数字，避免口头夸大

**完成标准：** 面试能拿出可复跑的数字，而不是「感觉挺准」。

---

## P1-4 可观测性

不必上完整 Grafana，但必须有一张能演示的数据图。

- [ ] Spring Actuator + Micrometer（健康、JVM、请求耗时）
- [ ] 结构化日志：`requestId`、用户/会话、Tool 名、耗时、错误码、是否 `fastMode`
- [ ] 暴露或汇总：接口错误率、AI 流式失败率、Tool 调用耗时、快速/正常模式首 Token
- [ ] 一份可展示的图或面板截图（Prometheus 文本 + 简单页面也可）
- [ ] 文档说明「如何在演示环境打开这张图」

---

## P1-5 契约、数据与资源保护

### OpenAPI 契约

- [ ] 用 OpenAPI 对齐 Java DTO 与 Python Pydantic，避免手工同步（含 `fastMode` / `memoryEnabled`）
- [ ] CI 校验契约漂移（字段增删必须失败）

### 数据库

- [ ] 引入 Flyway 或 Liquibase，取代「只靠手工 SQL 初始化」
- [ ] 列表接口补分页
- [ ] 准备一份可讲的 `EXPLAIN` / 索引优化案例（挂号、排班或会话查询）

### 限流与资源保护

- [ ] 聊天并发上限、单用户频率限制（同一 `conversationId` 并发写 checkpoint 目前未加锁，见 README）
- [ ] SSE 超时与取消
- [ ] 模型调用预算（次数 / Token）
- [ ] 文档上传限制大小，禁止一次性读入超大文件（[`ai-python/app/api/routes/chat.py`](ai-python/app/api/routes/chat.py)）
- [ ] 登录限流与 P0-2 合并验收

---

## P1-6 UI 小修（不改大视觉）

- [ ] 修复预约弹窗打开后焦点仍停留在背景按钮（[`frontend/src/views/Registration.vue`](frontend/src/views/Registration.vue)）
- [ ] 补全焦点陷阱；Escape 关闭弹窗
- [ ] 除健康助手外，补全站隐私说明 / 医疗免责声明入口
- [ ] 375px 移动端回归：首页、挂号、缴费、科室医生、健康助手（含快速模式开关）

---

## P2 辨识度功能：有安全边界的可执行 Agent

时间允许再做。UI 不大改，但能把项目从「接入大模型的医院系统」提升为「可执行 Agent」。

目标链路：

> AI 查询号源 → 生成挂号计划 → 用户确认 → 短期写权限 JWT → Java 事务锁号 → 幂等创建 → 审计记录 → LangGraph 恢复

- [x] LangGraph 接入 checkpointer，`conversationId` 作为 `thread_id`（HITL interrupt 的前置条件已就绪：委托令牌不进 State、回合字段重置、Shallow Redis checkpoint）
- [x] 快速模式作为第二条只读路径已落地，**不替代**下面的写操作闭环
- [ ] 挂号人工确认 interrupt（HITL），未确认不写库
- [ ] 确认后签发短期、最小权限写操作 JWT（scope + 患者绑定 + 过期）
- [ ] Java 事务锁号 + 幂等键创建挂号
- [ ] 审计记录（谁、何时、哪个号源、哪次会话、结果）
- [ ] 断线 / 刷新后可从 checkpoint 恢复待确认状态
- [ ] Tool 仍不能绕过 Java 直接写业务库
- [ ] 对应测试：确认前不落库、重复确认不重复挂号、过期 JWT 拒绝、跨患者拒绝
- [ ] 文档与流程图改回「已实现」，且能指到代码

**完成标准：** 现场演示「问号源 → 确认 → 真的挂上号 → 刷新会话仍在确认点」，并能讲清权限边界。

---

## 求职包装（穿插进行，勿等到最后）

- [ ] README 重写：一句话定位、架构图、技术栈、如何 5 分钟跑起来、能力边界（含快速模式）
- [ ] 补「面试可讲点」：权限边界、委托 JWT、RAG 引用校验（规则级，非医疗核验）、幂等与锁号、checkpoint 与快速/正常模式共用 thread
- [ ] 明确不要说的话：生产级医院系统、AI 能诊断、RAG 消除幻觉、高并发、医疗合规、AI 能直接挂号
- [ ] 简历条目按「场景 → 方案 → 结果」写，数字来自 Eval / E2E / 压测
- [ ] 准备 3 分钟现场演示脚本：首页 → 挂号 → 健康助手查内科号源 → 打开快速模式对比首 Token →（若已做）确认挂号

---

## 建议排期

| 阶段 | 内容 | 完成后项目状态 |
|---|---|---|
| 第 1 步 | P0-1 文档真实性 + 第 0 节改密码 | 不再被追代码打脸 |
| 第 2 步 | P0-2 HTTPS / 安全头 | 公网 Demo 可给面试官点 |
| 第 3 步 | P0-3 前端生产镜像 + Qdrant + 锁版本 | 仓库能复现线上 |
| 第 4 步 | P1-1 CI + P1-2 E2E + P1-3 Eval | 简历第一项目门槛 |
| 第 5 步 | P1-4 观测 + P1-5 契约/迁移/限流 + P1-6 UI | 工程完成度到 8 分档 |
| 第 6 步 | P2 HITL 写操作闭环 | Agent 岗主项目 |

---

## 完成前三步后的验收清单

- [ ] 文档与代码一致，测试数字可当场复跑
- [ ] 演示地址为 HTTPS 域名，登录不再走明文 HTTP
- [ ] `docker compose up --build` 能启动含 Redis、Qdrant 的完整栈
- [ ] 生产前端是 Nginx 静态托管，而不是 Vite dev
- [ ] CI 绿、E2E 能跑通登录和查号源
- [ ] 有一份可展示的 AI Eval 数字（含快速 vs 正常延迟）

达到以上即可作为秋招简历第一项目继续投递。
