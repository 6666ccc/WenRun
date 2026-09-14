package com.wenrun.ai.concurrency;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Redis-backed, owner-token protected conversation lease. */
@Component
@RequiredArgsConstructor
@ConditionalOnProperty(name = "wenrun.auth.session-store", havingValue = "redis")
@Slf4j
public class RedisConversationExecutionLock implements ConversationExecutionLock {

    private static final String KEY_PREFIX = "wenrun:ai:conversation-lock:";
    static final DefaultRedisScript<Long> RELEASE_SCRIPT = new DefaultRedisScript<>(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    + "return redis.call('del', KEYS[1]) else return 0 end",
            Long.class);
    static final DefaultRedisScript<Long> RENEW_SCRIPT = new DefaultRedisScript<>(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    + "return redis.call('pexpire', KEYS[1], ARGV[2]) else return 0 end",
            Long.class);
    private static final ScheduledExecutorService RENEWAL_EXECUTOR =
            Executors.newSingleThreadScheduledExecutor(runnable -> {
                Thread thread = new Thread(runnable, "ai-conversation-lock-renewal");
                thread.setDaemon(true);
                return thread;
            });

    private final StringRedisTemplate redisTemplate;

    @Value("${wenrun.ai.conversation-lock.lease:330s}")
    private Duration lease;

    @Value("${wenrun.ai.conversation-lock.renew-every:30s}")
    private Duration renewEvery;

    @Override
    public Optional<Handle> tryAcquire(Long userId, String conversationId) {
        String key = key(userId, conversationId);
        String ownerToken = UUID.randomUUID().toString();
        try {
            validateDurations();
            Boolean acquired = redisTemplate.opsForValue().setIfAbsent(key, ownerToken, lease);
            if (!Boolean.TRUE.equals(acquired)) {
                return Optional.empty();
            }
            AtomicBoolean closed = new AtomicBoolean(false);
            ScheduledFuture<?> renewal = RENEWAL_EXECUTOR.scheduleAtFixedRate(() -> {
                if (closed.get()) {
                    return;
                }
                try {
                    Long renewed = redisTemplate.execute(
                            RENEW_SCRIPT, List.of(key), ownerToken, String.valueOf(lease.toMillis()));
                    if (!Long.valueOf(1L).equals(renewed)) {
                        log.warn("AI conversation lock lease was lost key={}", key);
                    }
                } catch (RuntimeException ex) {
                    log.error("AI conversation lock renewal failed key={}", key, ex);
                }
            }, renewEvery.toMillis(), renewEvery.toMillis(), TimeUnit.MILLISECONDS);
            return Optional.of(() -> {
                if (!closed.compareAndSet(false, true)) {
                    return;
                }
                renewal.cancel(false);
                try {
                    redisTemplate.execute(RELEASE_SCRIPT, List.of(key), ownerToken);
                } catch (RuntimeException ex) {
                    log.error("AI conversation lock release failed key={}", key, ex);
                }
            });
        } catch (RuntimeException ex) {
            throw new ConversationLockUnavailableException("AI conversation lock is unavailable", ex);
        }
    }

    private void validateDurations() {
        if (lease == null || lease.isZero() || lease.isNegative()
                || renewEvery == null || renewEvery.isZero() || renewEvery.isNegative()
                || renewEvery.compareTo(lease) >= 0) {
            throw new IllegalStateException("Invalid AI conversation lock lease configuration");
        }
    }

    static String key(Long userId, String conversationId) {
        if (userId == null || conversationId == null || conversationId.isBlank()) {
            throw new IllegalArgumentException("Conversation lock identity is required");
        }
        return KEY_PREFIX + userId + ":" + conversationId;
    }
}
