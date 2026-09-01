package com.wenrun.config;

import com.wenrun.common.ResultCode;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.RedisConnectionFailureException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RedisTokenSessionStoreTest {

    private final Map<String, String> redis = new ConcurrentHashMap<>();
    private ValueOperations<String, String> ops;
    private RedisTokenSessionStore store;

    @BeforeEach
    void setUp() {
        store = new RedisTokenSessionStore(template(redis), Duration.ofHours(8));
    }

    @Test
    void createTokenStoresHashedKeyAndJsonPayload() {
        String token = store.createToken(7L, AccountType.PATIENT);

        String key = "wenrun:session:v1:" + sha256(token);
        String json = redis.get(key);
        assertNotNull(json);
        assertFalse(redis.containsKey(token));
        assertFalse(json.contains(token));
        assertTrue(json.contains("\"userId\":7"));
        assertTrue(json.contains("\"accountType\":\"patient\""));
        assertTrue(json.contains("\"issuedAt\""));
        assertFalse(json.toLowerCase().contains("password"));
        verify(ops).set(key, json, Duration.ofHours(8));
    }

    @Test
    void getUserIdAndAccountTypeRoundTrip() {
        String token = store.createToken(7L, AccountType.PATIENT);

        assertEquals(7L, store.getUserId(token));
        assertEquals(AccountType.PATIENT, store.getAccountType(token));
    }

    @Test
    void unknownTokenReturnsNull() {
        assertNull(store.getUserId("not-a-real-token"));
        assertNull(store.getAccountType("not-a-real-token"));
    }

    @Test
    void expiredKeyReturnsNull() {
        String token = store.createToken(7L, AccountType.PATIENT);
        redis.clear();

        assertNull(store.getUserId(token));
    }

    @Test
    void logoutRemovesSession() {
        String token = store.createToken(7L, AccountType.PATIENT);
        store.remove(token);

        assertNull(store.getUserId(token));
        assertTrue(redis.isEmpty());
    }

    @Test
    void secondInstanceCanReadSameSession() {
        String token = store.createToken(9L, AccountType.STAFF);
        RedisTokenSessionStore otherInstance = new RedisTokenSessionStore(template(redis), Duration.ofHours(8));

        assertEquals(9L, otherInstance.getUserId(token));
        assertEquals(AccountType.STAFF, otherInstance.getAccountType(token));
    }

    @Test
    void redisFailureOnReadReturnsNull() {
        StringRedisTemplate failing = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> failingOps = mock(ValueOperations.class);
        when(failing.opsForValue()).thenReturn(failingOps);
        when(failingOps.get(anyString())).thenThrow(new RedisConnectionFailureException("down"));
        RedisTokenSessionStore failingStore = new RedisTokenSessionStore(failing, Duration.ofHours(8));

        assertNull(failingStore.getUserId("any-token"));
    }

    @Test
    void redisFailureOnCreateThrowsUnavailable() {
        StringRedisTemplate failing = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> failingOps = mock(ValueOperations.class);
        when(failing.opsForValue()).thenReturn(failingOps);
        doAnswer(invocation -> {
            throw new RedisConnectionFailureException("down");
        }).when(failingOps).set(anyString(), anyString(), any(Duration.class));
        RedisTokenSessionStore failingStore = new RedisTokenSessionStore(failing, Duration.ofHours(8));

        BusinessException exception = assertThrows(BusinessException.class,
                () -> failingStore.createToken(1L, AccountType.PATIENT));
        assertEquals(ResultCode.SERVICE_UNAVAILABLE, exception.getCode());
        assertNotEquals("down", exception.getMessage());
    }

    @Test
    void blankTokenReturnsNullWithoutRedisWrite() {
        assertNull(store.getUserId(" "));
        assertNull(store.getUserId(null));
        assertTrue(redis.isEmpty());
    }

    private StringRedisTemplate template(Map<String, String> backing) {
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> valueOps = mock(ValueOperations.class);
        this.ops = valueOps;
        when(redisTemplate.opsForValue()).thenReturn(valueOps);
        when(valueOps.get(anyString())).thenAnswer(invocation -> backing.get(invocation.getArgument(0)));
        doAnswer(invocation -> {
            backing.put(invocation.getArgument(0), invocation.getArgument(1));
            return null;
        }).when(valueOps).set(anyString(), anyString(), any(Duration.class));
        when(redisTemplate.delete(anyString())).thenAnswer(invocation -> backing.remove(invocation.getArgument(0)) != null);
        return redisTemplate;
    }

    private static String sha256(String token) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
