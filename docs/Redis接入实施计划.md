# 在线医院项目 Redis 接入实施计划

> 目标：在不改变 MySQL 作为业务事实来源的前提下，引入 Redis 解决登录态单机化、AI 成本保护与热点查询压力问题；避免将医疗业务交易数据错误迁移到缓存。

## 1. 范围与原则

### 本期目标

1. 将 Java 进程内登录 Token 迁移为 Redis Session，支持服务重启与后续多实例部署。
2. 为登录和 AI 对话增加跨实例有效的限流与并发保护。
3. 缓存低频变更、高频读取的字典数据和短时 Dashboard 聚合数据。
4. 为 AI 重复请求增加短期“处理中”协调，避免重复调用模型。

### 非目标

- 不把用户、患者、挂号、排班、就诊、收费、处方、发药、库存等业务主数据迁移到 Redis。
- 不用 Redis 分布式锁替换 MySQL 事务、`SELECT ... FOR UPDATE` 或条件扣减。
- 不用 Redis 保存长期对话记录、知识库原文或 Qdrant 向量。
- 本期不实现 SSE 断线续传；只有未来 Java/Python 多实例且有恢复需求时再评估 Redis Streams。

### 设计原则

- **MySQL 是唯一事实来源**：所有涉及金额、状态流转、库存、号源和审计的写操作必须在 MySQL 事务中完成。
- **Redis 可以失效，业务不能失真**：缓存未命中时回源 MySQL；Redis 故障时，登录以外的缓存类能力应优雅降级。
- **缓存要有失效策略**：写入成功后主动删除关联缓存，TTL 仅作为兜底，不能只依赖过期时间。
- **密钥不进入仓库**：Redis 地址、密码、ACL 用户和 TLS 配置均使用环境变量或服务器密钥管理。

## 2. 当前代码基线

| 模块 | 当前实现 | 本计划的处理 |
| --- | --- | --- |
| 登录态 | `AuthTokenStore` 使用 `ConcurrentHashMap` 保存 UUID Token 和 8 小时过期时间 | 迁移为 Redis Session（P0） |
| AI 重复请求 | `chat_messages` 以用户、会话、请求 ID、角色建立唯一约束 | MySQL 保留最终幂等；Redis 只增加进行中协调（P1） |
| 挂号扣号 | MySQL 事务 + `SELECT ... FOR UPDATE` + 条件递减 | 保持不变，不迁移（禁止项） |
| 收费、处方、发药、库存 | MySQL 事务和状态流转 | 保持不变，不迁移（禁止项） |
| 字典查询 | 科室、诊疗项目、药品等每次查 MySQL | Cache-aside 缓存（P1） |
| Dashboard | 每次执行多条聚合 SQL | 10–30 秒短缓存（P1） |
| RAG | Qdrant 保存向量，Python 进程内缓存客户端和 Embedding | 保持不变，不迁移 |

## 3. 阶段一：Redis 基础设施与安全基线（P0）

### 3.1 部署位置（与 Qdrant 同机）

当前 Redis **与 Qdrant 部署在同一台机器**上，连接 host 取自现有 `QDRANT_URL` 的主机部分，仅端口不同。仓库 Compose 不创建 Qdrant，本期也不把 Redis 加进 Compose。

| 服务 | 配置来源 | 端口 | 访问方式 |
| --- | --- | --- | --- |
| Qdrant | `QDRANT_URL` | `6333` | HTTP，例如 `http://{host}:6333` |
| Redis | 与 `QDRANT_URL` 同一 `{host}` | `6379` | TCP，例如 `{host}:6379` |

解析 `{host}` 时与现有 Qdrant 保持一致：

- 本机进程直连：使用当前 `QDRANT_URL` 里的主机（局域网主机名、内网 IP 或 `localhost`）。
- Docker 容器访问该机器：与 Qdrant 示例相同，使用 `host.docker.internal` 或可解析的主机名。
- 不把 Redis `6379` 对公网开放，策略与当前 Qdrant 关闭公网端口一致。

host 相同不代表可以复用 Qdrant 的 URL 字符串：Redis 不是 HTTP 服务，Java 使用 host + port，不要把 `http://` 或 `:6333` 写进 Redis 配置。开发实例若尚未设置密码，用户名和密码可留空；生产仍须单独 ACL，不得沿用 Qdrant「无 API Key」的现状。

### 3.2 安全与运维基线

1. Redis 仅监听内网地址、局域网或私有网络，不对公网开放 `6379`。
2. 生产启用 ACL，单独创建应用账号；禁止使用默认账号承载应用流量。
3. 云服务支持时启用 TLS；Java 和 Python 均校验证书。本期同机开发实例若未启用 TLS，`SPRING_DATA_REDIS_SSL_ENABLED=false`。
4. 配置持久化策略与备份。Session 允许过期，但不能因主机重启而无计划丢失。
5. 设置 `maxmemory`、内存告警和连接数告警。建议把 Session/限流与可淘汰缓存隔离为不同实例或逻辑隔离的资源池。同机部署时尤其要注意 Redis 与 Qdrant 争用内存。
6. 不在日志中输出 Redis URL、密码、ACL 用户或业务 Token。真实 host、密码只写在被 Git 忽略的 `.env` 中。

### 3.3 项目配置

Java 新增环境变量。示例 host 与 `ai-python/.env.example` 中的 Qdrant 主机一致，端口改为 Redis：

```text
SPRING_DATA_REDIS_HOST=host.docker.internal
SPRING_DATA_REDIS_PORT=6379
SPRING_DATA_REDIS_USERNAME=
SPRING_DATA_REDIS_PASSWORD=
SPRING_DATA_REDIS_SSL_ENABLED=false
```

本地分别启动 Java 时，将 `SPRING_DATA_REDIS_HOST` 改成与当前 `QDRANT_URL` 相同的主机，不要写死仓库示例值。

Java 依赖增加 `spring-boot-starter-data-redis`。在 `application.yml.example` 和根目录 `.env.example` 中只保留环境变量引用，不写真实凭据或内网主机名。

### 3.4 验收标准

- Java 使用与当前 `QDRANT_URL` 相同的 host、端口 `6379` 可以连通 Redis。
- Redis 不可从公网访问。
- 密码、Token 与连接串不会出现在 Git、Compose 输出或应用日志中。
- Redis 重启、网络短暂异常的行为已在测试环境验证并有告警。

## 4. 阶段二：登录 Session 迁移（P0）

### 4.1 改造对象

将 `backend-java/src/main/java/com/wenrun/config/AuthTokenStore.java` 的进程内 Map 改为 Redis 实现，保留对 `AuthInterceptor` 和 `AuthService` 的现有调用接口，减少调用方改动。

### 4.2 键和值设计

| 项目 | 方案 |
| --- | --- |
| 键 | `wenrun:session:v1:{tokenHash}` |
| 值 | JSON：`userId`、`accountType`、`issuedAt`；不保存密码等敏感字段 |
| 过期 | Redis key TTL，默认沿用 `AUTH_TOKEN_TTL=8h` |
| 创建 | `SET key value EX ttl` |
| 鉴权读取 | `GET`，不存在即视为未登录或过期 |
| 登出 | `DEL key` |
| token 处理 | 浏览器仍持有随机不透明 Token；Redis 键使用 SHA-256 后的 token，减少运维侧意外暴露风险 |

### 4.3 实施步骤

1. 定义 `TokenSessionStore` 接口，并将当前内存实现保留为本地开发可选实现。
2. 新增 `RedisTokenSessionStore`，实现创建、查询、删除和 TTL 行为。
3. 更新 `AuthInterceptor`、`AuthServiceImpl` 的依赖注入。
4. 增加配置开关：本地无 Redis 时可显式使用内存实现；生产环境强制 Redis 实现，避免静默回退。
5. 补充单元测试与 Redis 集成测试：创建、过期、登出、服务实例切换、无效 Token。
6. 灰度发布后观察登录失败率、Redis 延迟和连接池指标。

### 4.4 验收标准

- 应用重启后，未过期 Token 仍可访问受保护接口。
- 两个 Java 实例可以验证同一个 Token；登出后均立即失效。
- Token 过期、篡改和 Redis 不可用时均返回明确且安全的未授权错误。

## 5. 阶段三：限流与 AI 并发保护（P0）

### 5.1 登录保护

使用 Redis 原子计数或令牌桶限制账号/IP 维度的失败登录：

| 键 | 建议规则 | TTL |
| --- | --- | --- |
| `wenrun:rl:login:ip:{ip}:{minute}` | 每 IP 每分钟 20 次请求 | 2 分钟 |
| `wenrun:login-fail:account:{accountHash}` | 连续失败 5 次后短暂冻结 | 15 分钟 |

冻结判断和计数更新必须使用原子命令或 Lua 脚本，避免多实例竞争。

### 5.2 AI 成本与容量保护

| 键 | 用途 | 建议初始策略 |
| --- | --- | --- |
| `wenrun:rl:ai:user:{userId}:{minute}` | AI 请求频率限制 | 每用户每分钟 6 次 |
| `wenrun:ai:active:user:{userId}` | 单用户活跃 SSE 数 | 最大 1 条，TTL 330 秒 |
| `wenrun:ai:active:global` | 全局模型流并发数 | 根据实例和供应商配额配置 |
| `wenrun:ai:turn:{userId}:{conversationId}:{clientRequestId}` | 同一轮请求处理中锁 | `SET NX EX 330` |

执行流程：请求先做频率检查，再申请并发名额和请求锁；SSE 的 `done`、`error`、断开、超时回调均释放名额。释放时要校验随机 owner 值，不能删除其他实例已续期的锁。

### 5.3 验收标准

- 多实例下同一用户不能并发建立多条 AI 流。
- 相同 `clientRequestId` 不会产生重复模型调用。
- 达到限制后返回 `429` 和可读错误信息，不占用 AI 线程池。
- 连接超时、浏览器主动断开、Python 调用异常后名额能自动释放或由 TTL 回收。

## 6. 阶段四：查询缓存（P1）

### 6.1 可缓存对象

| 数据 | 键示例 | TTL | 主动失效时机 |
| --- | --- | --- | --- |
| 科室列表 | `wenrun:cache:dept:list:{status}` | 30 分钟 | 新增、修改科室后 |
| 科室详情 | `wenrun:cache:dept:{id}` | 30 分钟 | 修改对应科室后 |
| 诊疗项目列表/详情 | `wenrun:cache:medical-item:*` | 15 分钟 | 新增、修改项目后 |
| 药品目录/详情 | `wenrun:cache:drug:*` | 15 分钟 | 新增、修改药品后 |
| Dashboard | `wenrun:cache:dashboard:{yyyy-MM-dd}` | 10–30 秒 | 挂号、收费、发药、库存相关写入后 |

采用 cache-aside：先查 Redis，未命中查询 MySQL 并写入缓存；业务写入完成后删除相关 key。缓存序列化统一使用 JSON，并明确版本前缀 `v1`，便于字段升级。

### 6.2 谨慎缓存对象

- 排班列表、剩余号源、药品库存列表：仅可用于展示，TTL 不超过 3–10 秒；提交挂号和扣减库存时必须回到 MySQL 重新校验。
- RAG 检索结果：仅未来对无用户上下文、知识库版本可识别的公开 FAQ 评估；本期不做。

### 6.3 不缓存对象

- 支付订单详情与支付结果。
- 当前患者的就诊、处方、挂号和收费记录。
- 完整个性化 AI 回答与医疗建议。

### 6.4 验收标准

- 缓存命中不会改变接口返回结构。
- 后台修改字典数据后，下一次读取不会长期返回旧数据。
- Redis 故障时，字典与 Dashboard 接口可回源 MySQL，而不是整体不可用。
- 通过指标可看到命中率、回源次数、序列化异常和缓存删除失败。

## 7. 必须保留在 MySQL/Qdrant 的数据与机制

| 内容 | 必须保留原因 |
| --- | --- |
| 挂号、排班剩余号源 | 依赖事务、行锁与条件扣减，不能接受缓存不一致 |
| 药品库存、处方、发药 | 涉及库存准确性、状态链路和审计 |
| 收费单、支付状态、收费明细 | 涉及金额，必须可追溯和事务一致 |
| 用户、患者、医护人员资料 | 关系数据和权限边界的事实来源 |
| `chat_messages` | 对话留存与 AI 请求幂等的最终依据 |
| 知识库文件与 Qdrant 向量 | Redis 不适合作为向量数据库或长期文档库 |

## 8. 幂等性与锁的边界

1. `registration` 表虽有 `idempotency_key` 唯一索引，但当前创建挂号 DTO 未传递该字段，服务也未赋值。本计划要求优先补齐 **MySQL 幂等写入**。
2. Redis 幂等键只用于快速拒绝重复中的请求，不能作为挂号、支付或发药的唯一防重手段。
3. 号源扣减继续使用 MySQL 的行锁与 `remaining_count > 0` 条件更新。Redis 锁不能替代数据库约束。
4. AI 消息继续以 MySQL 唯一索引作为最终幂等边界；Redis 仅防止重复消耗模型配额。

## 9. 可观测性与运维

新增指标和日志字段：

- Redis 请求耗时、错误率、连接池活跃数。
- Session 创建、命中、过期、登出次数；不得记录真实 Token。
- 限流拒绝次数，按 `login`、`ai`、`concurrency` 分类。
- 缓存命中率、回源次数、主动失效成功/失败次数。
- AI 活跃流数量、锁冲突次数、TTL 自动回收次数。

建议告警：Redis 连续连接失败、内存使用率过高、慢命令、连接耗尽、AI 429 异常增长、登录失败率异常增长。

## 10. 发布顺序与回滚

1. 使用与 Qdrant 同机的既有 Redis，完成连通性、安全、监控验证；不为本期单独新建云 Redis。
2. 先发布 Redis Session，保留短期可配置的内存实现回退开关。
3. 发布登录与 AI 限流，先以“只记录不拦截”模式观察一周，再开启实际拒绝。
4. 逐类启用字典缓存和 Dashboard 缓存；每类都先验证写后失效。
5. 最后引入 AI 请求处理中锁。

回滚原则：关闭缓存和限流开关即可回源原业务逻辑；Session 迁移需准备受控回滚窗口，并提前告知用户可能需要重新登录。绝不通过删除生产 Redis 全库作为常规回滚手段。

## 11. 完成定义（Definition of Done）

- Redis 连接、安全配置、监控和告警已验证。
- 登录 Session 已跨 Java 实例共享，重启不丢失未过期会话。
- 登录和 AI 限流在多实例下可重复验证。
- 静态字典和 Dashboard 缓存具备 TTL、主动失效和故障回源。
- 交易、库存、号源、支付、聊天持久化和 Qdrant 没有被错误迁移。
- 自动化测试覆盖 Redis 正常、过期、断连与竞争场景；README/运维文档已补齐环境变量和部署说明。
