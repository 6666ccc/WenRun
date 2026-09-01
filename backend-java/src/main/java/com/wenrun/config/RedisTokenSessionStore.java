package com.wenrun.config;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.UUID;

@Slf4j
@Component
@ConditionalOnProperty(name = "wenrun.auth.session-store", havingValue = "redis")
public class RedisTokenSessionStore implements TokenSessionStore {

    static final String KEY_PREFIX = "wenrun:session:v1:";

    private final StringRedisTemplate redis;
    private final Duration tokenTtl;
    private final ObjectMapper objectMapper;

    public RedisTokenSessionStore(StringRedisTemplate redis,
                                  @Value("${wenrun.auth.token-ttl:8h}") Duration tokenTtl) {
        this.redis = redis;
        this.tokenTtl = tokenTtl;
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    @Override
    public String createToken(Long userId, String accountType) {
        String token = UUID.randomUUID().toString().replace("-", "");
        SessionPayload payload = new SessionPayload(userId, accountType, Instant.now());
        try {
            redis.opsForValue().set(sessionKey(token), objectMapper.writeValueAsString(payload), tokenTtl);
        } catch (JsonProcessingException ex) {
            throw new BusinessException(ResultCode.INTERNAL_ERROR, "登录会话无法保存");
        } catch (DataAccessException ex) {
            log.warn("Redis session write failed: {}", ex.getClass().getSimpleName());
            throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE, "登录服务暂不可用，请稍后重试");
        }
        return token;
    }

    @Override
    public Long getUserId(String token) {
        SessionPayload session = getValidSession(token);
        return session == null ? null : session.userId();
    }

    @Override
    public String getAccountType(String token) {
        SessionPayload session = getValidSession(token);
        return session == null ? null : session.accountType();
    }

    @Override
    public void remove(String token) {
        if (!StringUtils.hasText(token)) {
            return;
        }
        try {
            redis.delete(sessionKey(token));
        } catch (DataAccessException ex) {
            log.warn("Redis session delete failed: {}", ex.getClass().getSimpleName());
            throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE, "登录服务暂不可用，请稍后重试");
        }
    }

    private SessionPayload getValidSession(String token) {
        if (!StringUtils.hasText(token)) {
            return null;
        }
        String key = sessionKey(token);
        try {
            String json = redis.opsForValue().get(key);
            if (!StringUtils.hasText(json)) {
                return null;
            }
            return objectMapper.readValue(json, SessionPayload.class);
        } catch (JsonProcessingException ex) {
            try {
                redis.delete(key);
            } catch (DataAccessException ignored) {
                // 损坏的会话视为无效即可
            }
            return null;
        } catch (DataAccessException ex) {
            log.warn("Redis session read failed: {}", ex.getClass().getSimpleName());
            return null;
        }
    }

    static String sessionKey(String token) {
        return KEY_PREFIX + sha256(token);
    }

    private static String sha256(String token) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    record SessionPayload(Long userId, String accountType, Instant issuedAt) {
    }
}
