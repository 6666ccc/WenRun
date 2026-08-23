package com.wenrun.config;

import org.springframework.stereotype.Component;

import org.springframework.beans.factory.annotation.Value;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 内存 Token 存储（毕设简化，重启失效）
 */
@Component
public class AuthTokenStore {

    private final Map<String, TokenSession> tokenSessionMap = new ConcurrentHashMap<>();
    private final Duration tokenTtl;

    public AuthTokenStore(@Value("${wenrun.auth.token-ttl:8h}") Duration tokenTtl) {
        this.tokenTtl = tokenTtl;
    }

    public String createToken(Long userId) {
        return createToken(userId, null);
    }

    public String createToken(Long userId, String accountType) {
        String token = UUID.randomUUID().toString().replace("-", "");
        tokenSessionMap.put(token, new TokenSession(userId, accountType, Instant.now().plus(tokenTtl)));
        return token;
    }

    public Long getUserId(String token) {
        TokenSession session = getValidSession(token);
        return session == null ? null : session.userId();
    }

    public String getAccountType(String token) {
        TokenSession session = getValidSession(token);
        return session == null ? null : session.accountType();
    }

    public void remove(String token) {
        tokenSessionMap.remove(token);
    }

    private TokenSession getValidSession(String token) {
        TokenSession session = tokenSessionMap.get(token);
        if (session != null && !Instant.now().isBefore(session.expiresAt())) {
            tokenSessionMap.remove(token, session);
            return null;
        }
        return session;
    }

    private record TokenSession(Long userId, String accountType, Instant expiresAt) {
    }
}
