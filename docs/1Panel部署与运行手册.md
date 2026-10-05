# 1Panel 部署与运行手册

本仓库采用 Compose 管理五个容器，1Panel OpenResty 负责域名与 HTTPS。前端提供静态文件及 `/api` 代理，Java/Python/MySQL/Redis 不发布宿主机端口。仅前端加入面板共享网络，另提供宿主机回环端口 `127.0.0.1:18080` 供本机验收。

流程依据 [1Panel 编排](https://1panel.cn/docs/v2/user_manual/containers/compose/)与[反向代理网站](https://1panel.cn/docs/v2/user_manual/websites/website_create/)文档。流式代理设置依据 [Nginx proxy 模块](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)。操作界面可能随面板版本变化，以实际界面为准。

## 1. 部署前准备

服务器需要 Docker Compose V2、1Panel OpenResty；执行本手册脚本还需要 Python 3。将完整项目上传到固定目录，例如 `/opt/wenrun`，保留 `frontend/package-lock.json` 与 `ai-python/requirements.lock`。

本机未安装 Docker：目前已验证源码测试、Java 打包、Python wheel、部署脚本和 YAML 结构；镜像构建、真实容器启动、域名 HTTPS 尚未在本地执行。CI 已加入真实容器栈启动与只读烟测，需推送后查看运行结果。

2026-10-04 本地收尾验证：Python 全量 360 项、Java clean verify 165 项、前端 84 项及 lint/build 通过；上下文 30 个确定性样本和 32 项故障测试通过。Compose 已按官方规范 schema 校验；容器构建与启动仍不能视为已验证。

新部署使用独立 MySQL 8.4、Redis 8，不自动复用面板现有数据库。Redis 8 包含 checkpoint 所需的 JSON/Search；db0 为 Python checkpoint，db1 为 Java Session/会话锁。原文件、Chroma 和分词器缓存保存在 `ai-data` 卷，SQL 保存在 `mysql-data`，Redis AOF/RDB 保存在 `redis-data`。

如果必须复用 1Panel 的 MySQL/Redis，应另行调整服务网络和连接配置，确认 Redis 版本及 JSON/Search，迁移应用库并使用独立应用账号；不要直接把服务名改成宿主机 localhost。

### 配置环境变量

根目录现有 `.env` 可能是旧开发配置，先在私有位置备份，确认后再换用 `deploy/.env.example`；生成器拒绝覆盖已有文件。

```sh
cd /opt/wenrun
python3 deploy/configure.py --origin https://你的域名 --env .env.deploy
chmod 600 .env.deploy
# 私下编辑 .env.deploy，填 DASHSCOPE_API_KEY、聊天模型和 Embedding 模型。
# 核对之后复制到根目录 .env（先备份原文件）。
```

生成器自动创建不同的 MySQL root/应用密码、Redis 密码、服务间密钥和 Base64 委托密钥，不打印凭证。根 `.env` 仅用于 Compose；现有 `ai-python/.env` 不会打进镜像。应用容器从 Compose 接收所需变量，默认关闭 Agent 正文日志。

填写 `PANEL_NETWORK` 为 OpenResty 实际所在的 Docker 网络，可在 1Panel 容器详情或 `docker inspect` 中确认。默认 `1panel-network`；此网络须已存在。前端与 OpenResty 必须在同一网络，代理目标为 `http://wenrun-web:80`。OpenResty 容器中的 `127.0.0.1` 指向它自身，不能用来访问本应用容器。

初期不打包 Ollama。Jev key 留空且无本地分类服务时使用既有云端路由降级；如需 Jev 或公开搜索，再填写对应 key。

### 启动

```sh
cd /opt/wenrun
python3 deploy/preflight.py
docker compose up -d --build --wait --wait-timeout 300
python3 deploy/smoke.py
```

预检检查必要字段、重复变量、密码/委托密钥格式、Compose 配置和面板网络，避免输出展开后的凭证。可在无 Docker 环境用 `--static-only` 仅检查文件和变量。

1Panel 可通过“容器 → 编排 → 路径选择”导入根目录 `compose.yaml`；必须保留项目根路径和 `.env`，不要仅粘贴 YAML 到其他目录，否则构建上下文、初始化 SQL 和配置挂载路径会改变。若界面版本仅列出固定文件名，可通过终端使用上面的命令管理，再在面板查看容器。

首次空卷初始化只导入 `docs/SQL/schema.sql`，**不导入测试账号或 seed.sql**。已有数据库必须备份并核对已执行迁移；不能再次灌入建表脚本当作自动升级。

首次知识库切分需要下载 Qwen 分词器，建议开放站点前预热缓存：

```sh
docker compose exec -T ai-python python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')"
```

此步骤下载分词器，不执行付费 Embedding 或聊天请求；服务器无法访问 Hugging Face 时，先在可联网环境下载同一缓存，再导入 `ai-data` 卷内 `/app/data/huggingface`。不要用不对应的分词器替代后直接沿用旧切分预算。

## 2. 1Panel 网站与 SSE

创建反向代理网站，绑定域名、设置上游 `http://wenrun-web:80`，申请并启用 HTTPS。合并 [OpenResty 配置示例](../deploy/1panel-openresty.conf)到面板生成的代理 location，避免重复添加 `location /`。代理关闭响应缓冲和缓存、设置 360 秒读写超时并禁止自动重试；这与应用内 Nginx 保持一致，避免整段输出最后才出现或业务 POST 被代理重试。

配置示例用 Docker DNS 动态解析上游，应用容器重建换 IP 后不必重载代理。检查 OpenResty 配置成功后再重载；若网络地址不在 Docker 常见私有网段中，调整 `deploy/nginx.conf` 的可信代理网段，使登录限流按真实客户端计数。未可信的转发头不能作为客户端身份。

只开放面板管理所需入口与网站 80/443。不要另行发布 MySQL、Redis、Java、Python 端口；内部工具 `/api/internal/**` 与 Java readiness 在前端代理处直接返回 404。

## 3. 健康检查与验收

| 检查 | 含义 |
| --- | --- |
| 前端 `/healthz` | Nginx 响应 |
| Java `/api/health` | Java HTTP 存活 |
| Java `/api/health/ready`（仅容器内） | MySQL 与 Redis 可响应 |
| Python `/health` | Python HTTP 存活 |
| Python `/ready`（仅容器内） | checkpoint 已初始化、RAG Worker 在运行、权威库可访问且 Redis 可响应 |

readiness 不调用外部模型，不证明 API key 额度、医学回答质量或 Embedding 可用。Docker unhealthy 只显示故障，`unless-stopped` 只重启退出的进程；应在 1Panel/监控中配置健康异常告警，不将其误认为自动恢复。

烟测检查 SPA 路由、Java 代理、匿名会话访问拒绝和内部接口屏蔽。可通过私有环境变量 `WENRUN_SMOKE_TOKEN` 添加已有测试账号的会话读取；脚本不打印 token 或患者响应正文，不创建预约、不发起付费模型调用。

开放给真实用户前，使用专用测试账号完成下列验收，并记录日期、镜像版本和结果：

1. 注册/登录、退出、患者切换；不同账号互相访问档案和会话被拒绝。
2. 普通/快速聊天、中文输出与来源；真实域名下逐段 SSE 到达，停止与断流可恢复操作。
3. 查真实号源、确认挂号、重复点击不重复挂号、拒绝不写入、退号；确认前后号源变化返回事务真实结果。
4. 应用重启后历史和摘要仍可读；测试环境中丢弃指定会话 checkpoint，确认旧卡片不可执行、数据库历史可恢复。
5. 上传代表性 PDF/DOCX，审核并发布；检查章节、表格、公式和引用。未来版本到期后由 Worker 周期激活，索引异常会保留 scheduled 记录并重试。
6. 实际执行一次备份与隔离环境恢复，并确认档案、会话、摘要、原文件和引用均可读取。

对第 3～6 项先在测试库操作。历史 PDF 版面/多公式问题尚未在本次收尾重新做真实资料验收；合成测试通过不能代替人工核对。没有真实问答标注集，不宣称线上准确率或召回率。

## 4. 升级与回滚

Python 运行依赖锁定于 `requirements.lock`（目标 Linux x86_64/Python 3.13），前端使用 `npm ci`。基础镜像采用版本系列标签，发布前记录实际镜像 ID；需要严格复现时改用已测试 digest。ARM 服务器需重新解析锁文件并完成构建与验收。

```sh
docker compose ps
# 备份完成后，核对本次 SQL 迁移，再更新代码。
# 私下编辑 .env 的 RELEASE_TAG 为新的唯一版本，例如 release-20261004。
docker compose build
docker compose up -d --wait --wait-timeout 300
python3 deploy/smoke.py --url https://你的域名
```

保存旧版本代码、`.env` 与旧应用镜像，不立即 prune。回滚应用时切回旧代码和 RELEASE_TAG，使用 `docker compose up -d --no-build --wait`；先确认旧代码兼容迁移后的 schema。应用回滚不等于数据库回滚，破坏性迁移必须另行准备并演练恢复。不要使用 `docker compose down -v`，该命令会删除业务卷。

## 5. 备份与恢复

在运行中的栈上执行：

```sh
cd /opt/wenrun
sh deploy/backup.sh /绝对路径/备份目录
```

脚本短暂停止前端、Java、Python，捕获同一写入边界的 MySQL 导出与 AI 数据卷；Redis SAVE 后停机打包 RDB/AOF，避免拷贝正在重写的 AOF。退出时重新启动服务，之后运行烟测。备份同时保存私有部署 env、Git revision 和镜像清单，以 `SHA256SUMS` 检查 SQL/数据包。

备份含患者资料和凭证，权限为私有，须加密后复制到异机或对象存储；面板所在磁盘的一份压缩包不构成灾备。设定备份周期与保留时间后，在 1Panel 的计划任务中调用脚本；运行时间应避开业务高峰，因为此方案有短暂维护窗口。

恢复演练使用独立服务器或隔离测试环境：

1. 复制相应版本代码和镜像，恢复私有 `.env`，核对域名/面板网络；验证备份校验和。
2. 在空数据卷启动 MySQL 并等待健康。停止应用，用下列方式导入 SQL。
3. 解压 AI 数据包到挂载的 `/app/data`，恢复 Redis 数据包到 `/data`；操作时应用与 Redis 必须停止。
4. 启动栈并检查健康与烟测，再人工核对上述业务和恢复场景。不要在已有生产卷上练习。

```sh
# 以下命令只在隔离恢复环境使用，bundle 为已验证的备份目录。
docker compose up -d --wait mysql
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -u root wenrun' < "$bundle/mysql.sql"
docker compose run --rm --no-deps -T --user 0 --entrypoint tar ai-python -C /app/data -xzf - < "$bundle/ai-data.tar.gz"
docker compose run --rm --no-deps -T --user 0 --entrypoint tar redis -C /data -xzf - < "$bundle/redis-data.tar.gz"
docker compose up -d --wait --wait-timeout 300
```

MySQL 是消息和摘要事实源；Redis checkpoint 允许丢失，丢失时不能恢复挂起的业务确认。Chroma 可重建，但原文件、解析产物与权威登记须一起保留。
