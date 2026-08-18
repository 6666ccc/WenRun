package com.wenrun.config;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 内存 Token 存储（毕设简化，重启失效）
 */
@Component
public class AuthTokenStore {

    private final Map<String, TokenSession> tokenSessionMap = new ConcurrentHashMap<>();

    public String createToken(Long userId) {
        return createToken(userId, null);
    }

    public String createToken(Long userId, String accountType) {
        String token = UUID.randomUUID().toString().replace("-", "");
        tokenSessionMap.put(token, new TokenSession(userId, accountType));
        return token;
    }

    public Long getUserId(String token) {
        TokenSession session = tokenSessionMap.get(token);
        return session == null ? null : session.userId();
    }

    public String getAccountType(String token) {
        TokenSession session = tokenSessionMap.get(token);
        return session == null ? null : session.accountType();
    }

    public void remove(String token) {
        tokenSessionMap.remove(token);
    }

    private record TokenSession(Long userId, String accountType) {
    }
}
