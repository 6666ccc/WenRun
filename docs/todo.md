# 线上问题备忘：AI 确认挂号失败 + 挂号记录“消失”

> 历史事故记录：下文保留 2026-09-04 当时的日志与旧实现描述，不代表当前代码。用户作用域 thread、interruptId 恢复、HITL 写工具和会话锁现已落地；当前事实以根 README 和 AI 运维指南为准。

记录时间：2026-09-04  
环境：`/home/ubuntu/image` Docker Compose（`wenrun-backend-java` / `wenrun-ai-python` / Redis Stack）  
本文只描述现象、日志证据和改法建议，不改代码。

---

## 1. 刚才这次：助手里确认挂号失败

### 1.1 用户看到的现象

在健康助手里走完选号，弹出「确认挂号」卡片，点确认后对话失败（前端文案大致是「AI 对话处理失败，请稍后再试」）。挂号记录没有新增。

容器当时都是 Up，没有 OOM、没有重启。

### 1.2 实际请求链（北京时间 15:30 前后，容器日志为 UTC）

Java 全程 HTTP 200，**没有 ERROR / WARN**。断点在 Python 续跑图，不在挂号业务接口。

| 北京时间 | 服务 | 发生了什么 |
|---------|------|------------|
| 15:30:37 | Java `POST /api/ai/chat/stream` → Python `/v1/chat/stream` | 走 tools，查科室和号源，正常结束 |
| 15:30:51 | 同上 | 再查科室 / 医生 / 号源，并 `GET /api/internal/ai-tools/schedules/58` |
| 15:30:59 | Python | `chat_stream_awaiting_confirmation kind=registration_create`，前端出确认卡 |
| 15:31:02 | Java `POST /api/ai/chat/resume` 200 | 只是把 resume 转给 Python |
| 15:31:02 | Python `/v1/chat/resume` | **内部立刻异常**，没有再调 `POST /api/internal/ai-tools/registrations` |

对比：**当天 08:46** 同一条链路是成功的。确认后 Java 会继续：

- `GET /api/internal/ai-tools/schedules/67`
- `POST /api/internal/ai-tools/registrations`（200，真正落库）

刚才这次在 resume 进图时就炸了，所以 Java 挂号接口根本没被打到。不能从「Java 没有报错」推断挂号成功。

### 1.3 Python 异常

```text
ERROR  app.api.routes.chat:_chat_events:343
chat_stream_failed conversation_id=default

RuntimeError: When there are multiple pending interrupts,
you must specify the interrupt id when resuming.
Docs: https://docs.langchain.com/oss/python/langgraph/add-human-in-the-loop
      #resume-multiple-interrupts-with-one-invocation
```

栈在 `graph_instance.astream(...)` → `AsyncPregelLoop.__aenter__` → `_first()`。  
也就是 **续跑还没执行写工具**，LangGraph 就拒绝这次 resume。

### 1.4 代码上为什么会炸

挂号写工具在提交前用 `interrupt()` 等人确认：

- `create_registration`：`kind=registration_create`
- `cancel_registration`：`kind=registration_cancel`

Python `chat_resume` 当前写法：

```python
graph_input=Command(resume=request.decision)  # 只有 "approve" / 拒绝，没有 interrupt id
config={"configurable": {"thread_id": conversation_id}}
```

LangGraph 的规则：同一 thread 上如果 **挂起的 interrupt 超过一个**，`Command(resume=值)` 非法，必须：

```python
Command(resume={interrupt_id: decision})
```

另外，所有日志里的会话都是：

```text
conversation_id=default
thread_id=default
```

checkpoint 存在 Redis（compose 里 Python / Java 共用 `redis/redis-stack-server`）。  
**所有人、所有轮对话若共用 `default`，interrupt 和记忆会串在同一条 thread 上。**

`_pending_confirmation()` 只返回快照里 **第一个带 `kind` 的 interrupt**。  
前端因此只显示一张确认卡；用户点确认时，checkpoint 里可能已经有两张挂起，resume 必失败。

### 1.5 这次「多个 interrupt」从哪来（推断，按可能性）

1. **同一 thread 残留（最像）**  
   08:46 已经成功确认过一次挂号（当时也是 `conversation_id=default`）。checkpoint TTL 日志是 `ttl_minutes=1440`（24 小时）。  
   下午再开一轮，15:30:59 又挂起一个 `registration_create`。resume 时新旧 interrupt 叠在一起。

2. **同一轮并行写工具**  
   模型在一轮里同时调了 `create_registration` 和 `cancel_registration`（或两次 create）。每个 `interrupt()` 一张挂起。  
   这次 Java 在确认前只看到一次 `GET .../schedules/58`，更像只有一个 create 走到了 interrupt；不能完全排除并行，但不如 1 干净。

3. **新 stream 打在仍处于 interrupt 的 thread 上**  
   15:30:37 那轮标记为 completed，不像未确认挂起。优先级低于 1。

### 1.6 见解（根因）

这不是号源接口坏了，也不是 Java 挂号事务失败。

是 **人机确认（HITL）和会话隔离没做完**：

- 写工具依赖 LangGraph interrupt + Redis checkpoint，这条是对的。
- resume 按「单 interrupt」写死了，没有按官方多 interrupt API 恢复。
- `conversation_id` 用死 `default`，等于全站一条 thread。只要出现第二次确认、确认未完成又开新对话、或并行写工具，下午这种炸法会再出现。
- Java 把 Python 的 SSE 包装成 200，**HTTP 成功 ≠ 图跑完 ≠ 挂号落库**。排障必须看 Python `chat_stream_failed`，以及确认后有没有 `POST .../registrations`。

### 1.7 建议改法（优先顺序）

**P0 会话隔离**

- 前端 / Java 为每个登录用户、每次助手会话生成稳定且唯一的 `conversation_id`（例如 `userId + uuid`），不要再用 `default`。
- Java 已有 `ConversationOwnershipService`，应强制 conversation 归属当前用户，禁止跨用户复用 thread。

**P0 resume 带 interrupt id**

- 下发 `confirm` 事件时带上该 interrupt 的 id。
- `POST /resume` 使用 `Command(resume={id: decision})`。
- 若检测到多个 pending interrupt：要么只恢复当前卡片对应的那张，要么拒绝并提示「请重新发起挂号」，同时 `adelete_thread`。

**P1 脏 checkpoint**

- 新 `/stream` 打到仍有 pending interrupt 的 thread：先结束/清理旧挂起，或直接换新 `conversation_id`。
- 给前端一个「新对话」会调 `DELETE /memory/{conversation_id}`。
- 线上急救：清 Redis 里 thread `default` 的 checkpoint，或换一个 conversation_id 再试（不修代码的话，旧会话上继续点确认还会炸）。

**P1 可观测性**

- Java `RequestTraceFilter` 现在只打 path，resume/stream 成功时看不到 Python 是否失败。至少打 `conversation_id`、resume 后是否真正 `POST registrations`。
- Python 在 resume 前打：pending interrupt 数量、各自 id / kind。多 interrupt 时不要只丢通用 500。

**P2 产品**

- 一轮只允许一个写工具（create 或 cancel），降低并行 interrupt。
- 确认卡超时或离开页面时清理 thread。

### 1.8 线上急救（不改镜像）

1. 不要在当前 `default` 会话上反复点确认。  
2. 清 Redis 中 LangGraph checkpoint（thread `default`），或重启 `wenrun-redis`（会丢掉所有会话记忆，24h TTL 内的都在这）。  
3. 用页面挂号，不走助手，可绕过 HITL。

---

## 2. 前一天相关：页面挂号成功，但「待就诊」看不到

这是另一条 bug，容易和上面那次「没挂上」搞混。当时 Java 也是 200。

### 2.1 现象

页面预约提示成功，个人中心「待就诊」为空。库里其实有单，状态是 **3 = 已退号**。

例（2026-09-03）：

- `POST /api/registrations` 200 → 单号 13、14
- `GET /api/registrations` 200
- 13/14 的 `schedule_id` 为 1、3，就诊日 **2026-09-01**（已过期）
- `status` 随后变成 3

### 2.2 原因

1. 号源列表不过滤过期排班，能挂到昨天/前天的号。  
2. Java `RegistrationServiceImpl.list()` 在 **查询列表时** 把「已挂号 + 排班已过期」改成已退号。  
3. 前端「待就诊」/ 首页当前挂号只认 `status === 1`，所以看起来像没挂上。  
4. 列表查询时的自动退号会把「已挂号 + 排班已过期」改成已退号。当前实现已在抢到状态流转后 `incrementRemaining` 还号；历史上曾只改 status、不还号。

助手侧 `create_registration` 已有 `slot_is_expired()`，过期排班不会提交。页面挂号同样在 `RegistrationServiceImpl.register()` 拒绝过期排班，`GET /api/schedules` 默认 `work_date >= today`。

### 2.3 建议

- `GET /api/schedules` 默认 `work_date >= today`（业务日期走 `ClinicProperties` 的 `Asia/Shanghai`；容器应设 `TZ=Asia/Shanghai`，避免 `LocalDateTime.now()` 跟 JVM 默认 UTC）。  
- `POST /api/registrations` 拒绝过期排班。  
- 过期自动退号已还号；若以后要拿掉 GET 副作用，可改成定时任务。  
- 个人中心列表已包含已退号；若产品只想看待就诊，空态文案不要写成「还没有挂号记录」。

---

## 3. 排障时不要踩的坑

- Java access log 200 ≠ 业务成功。AI 场景看 Python；挂号落库看 `registration` 表和有没有 `POST .../registrations`。  
- 三个 tar 的文件名不等于镜像 tag。曾出现 `wenrun-backend-java.tar` 实际是 `wenrun/ai-python:latest`（体积约 120MB 且 RepoTags 不对）。Java 包正常约 144MB，tag 必须是 `wenrun/backend-java:latest`。  
- 容器未设 `TZ` 时日志是 UTC，北京时间 +8。compose 已为 Java / Python 设 `TZ=Asia/Shanghai`。

---

## 4. 建议开发侧落地的 TODO

- [x] 助手会话不再使用 `conversation_id=default`，按用户 + 会话隔离 Redis thread
- [x] `POST /v1/chat/resume` 按 interrupt id 恢复；多 interrupt 时明确报错或清理 thread
- [x] `confirm` SSE 带上 interrupt id，前端 resume 原样传回
- [x] 新 `/stream` 打到仍有 pending interrupt 的 thread 时删除旧 checkpoint；删会话仍走 `DELETE /memory/{id}`
- [x] Java 代理 AI 流时记录 Python 业务失败（`error` / `confirm` / `done` 打 `conversationId`，不能只看 HTTP 200）
- [x] 页面号源与挂号接口拒绝过期排班；自动退号要还号
- [x] JVM / 业务日期统一 `Asia/Shanghai`，避免 UTC 切日和排班日期不一致
