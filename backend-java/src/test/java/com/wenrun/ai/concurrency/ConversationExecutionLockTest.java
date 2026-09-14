package com.wenrun.ai.concurrency;

import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ConversationExecutionLockTest {

    @Test
    void inMemoryLockSerializesOnlyTheSameUserConversationPair() {
        InMemoryConversationExecutionLock lock = new InMemoryConversationExecutionLock();

        ConversationExecutionLock.Handle first = lock.tryAcquire(7L, "shared-id").orElseThrow();
        assertThat(lock.tryAcquire(7L, "shared-id")).isEmpty();
        assertThat(lock.tryAcquire(8L, "shared-id")).isPresent();

        first.close();
        ConversationExecutionLock.Handle second = lock.tryAcquire(7L, "shared-id").orElseThrow();
        first.close();
        assertThat(lock.tryAcquire(7L, "shared-id")).isEmpty();
        second.close();
    }

    @Test
    void redisLockUsesTenantScopedKeyAndLease() {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> values = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(values);
        when(values.setIfAbsent(eq("wenrun:ai:conversation-lock:7:conversation-1"), any(String.class),
                eq(Duration.ofSeconds(330)))).thenReturn(true);
        RedisConversationExecutionLock lock = new RedisConversationExecutionLock(redis);
        ReflectionTestUtils.setField(lock, "lease", Duration.ofSeconds(330));
        ReflectionTestUtils.setField(lock, "renewEvery", Duration.ofSeconds(30));

        ConversationExecutionLock.Handle handle = lock.tryAcquire(7L, "conversation-1").orElseThrow();
        handle.close();
    }

    @Test
    void redisLockDoesNotTreatAnUnavailableRedisAsAnUnlockedConversation() {
        StringRedisTemplate redis = mock(StringRedisTemplate.class);
        when(redis.opsForValue()).thenThrow(new IllegalStateException("redis down"));
        RedisConversationExecutionLock lock = new RedisConversationExecutionLock(redis);
        ReflectionTestUtils.setField(lock, "lease", Duration.ofSeconds(330));
        ReflectionTestUtils.setField(lock, "renewEvery", Duration.ofSeconds(30));

        assertThatThrownBy(() -> lock.tryAcquire(7L, "conversation-1"))
                .hasMessageContaining("unavailable");
    }

    @Test
    void redisScriptsCompareOwnerBeforeRenewingOrReleasing() {
        assertThat(RedisConversationExecutionLock.RENEW_SCRIPT.getScriptAsString())
                .contains("redis.call('get', KEYS[1]) == ARGV[1]")
                .contains("pexpire");
        assertThat(RedisConversationExecutionLock.RELEASE_SCRIPT.getScriptAsString())
                .contains("redis.call('get', KEYS[1]) == ARGV[1]")
                .contains("del");
    }
}
