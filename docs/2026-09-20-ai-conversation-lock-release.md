# 2026-09-20 AI 会话锁释放被中断

现象出现在本地联调：助手已经正常 `done` 并落库，Java 仍打 ERROR `AI conversation lock release failed` / `Redis command interrupted`。不是 Redis 宕机。

## 现象

- 日志线程：`ai-stream-*`
- 日志：`c.w.a.c.RedisConversationExecutionLock : AI conversation lock release failed key=wenrun:ai:conversation-lock:{userId}:{conversationId}`
- 异常：`org.springframework.data.redis.RedisSystemException: Redis command interrupted`
- 根因异常：`io.lettuce.core.RedisCommandInterruptedException` ← `java.lang.InterruptedException`
- 典型时间线（同一秒内）：先有 `ai_stream_event type=done`，再 `ChatMessageRepository.insert` 助手消息成功，最后 `lock.close()` 失败

本轮实例：`2026-09-20T11:58:04`，`userId=5`，`conversationId=session_1789875969021_781b6b0c3119e`。`done` 在 `.401`，助手消息写入在 `.416`，锁释放失败在 `.663`。

## 影响

- 患者侧这一轮已经结束，回复可见。
- Redis 键 `wenrun:ai:conversation-lock:{userId}:{conversationId}` 可能残留到租约到期（默认 330s）。
- 同一会话在锁未过期前再发消息，可能误报 `AI_CONVERSATION_BUSY`（「该会话正在处理上一条消息」）。

## 根因

Java 网关用 `SseEmitter` 转发 Python SSE，并用 Redis 会话锁保证同一 `userId + conversationId` 同时只跑一轮。工作线程在 `finally` 里 `lock.close()`。

原先 `onTimeout` / `onError` / `onCompletion` 都走 `task.cancel(true)`。`emitter.complete()` 会在**同一条工作线程上同步**触发 `onCompletion`，于是：

1. 收到 `done`（或 `confirm` / `error`）后调用 `emitter.complete()`
2. `onCompletion` → `Future.cancel(true)` 打断当前 `ai-stream` 线程
3. `finally` 里 Lettuce 同步 `EVALSHA` 释放锁，发现中断标记，直接失败
4. 锁没删掉

超时或客户端断开仍需要 `cancel(true)`，用来打断还在读 Python 流的阻塞调用。只有「本线程自己 complete」这条路径不能打断自己。

另有一条较快的竞态：HTTP 线程在 `submit` 之后若看见 `terminal=true` 就 `cancel(true)`。正常结束也会把 `terminal` 置位，可能在 `lock.close()` 期间再次打断工作线程。只有超时/断开（`abort`）才应在登记 Future 后补一次中断。

## 处理

代码：

- `aiController.stream`：`onCompletion` 只标 `terminal`，不 `cancel(true)`；`onTimeout` / `onError` 仍中断上游。`submit` 之后只在 `abort` 时补 `cancel(true)`。
- `RedisConversationExecutionLock.close`：释放前 `Thread.interrupted()` 清标记，执行 `RELEASE_SCRIPT`，再按原状态恢复中断。避免 Lettuce 把清理当成失败。

测试：

- `ConversationExecutionLockTest.redisLockReleaseClearsCallerInterruptSoLettuceCanFinish`
- `AiControllerConcurrencyTest.completedStreamDoesNotInterruptLockRelease`

改完后需重启正在跑的 Java 进程，否则仍是旧字节码。

## 以后怎么认

再看到这条 ERROR，先对一下同一 `conversationId` 是否已经有 `type=done` / `confirm`。若助手消息已写入，优先怀疑完成回调打断了释放，而不是 Redis 本身不可用。锁获取失败才是 `ConversationLockUnavailableException` / `AI_CONVERSATION_LOCK_UNAVAILABLE`。

相关实现：`backend-java/src/main/java/com/wenrun/ai/controller/aiController.java`、`backend-java/src/main/java/com/wenrun/ai/concurrency/RedisConversationExecutionLock.java`。协议说明见 `docs/learn.md` §4.3、`docs/AI模块开发与运维指南.md` §7。
