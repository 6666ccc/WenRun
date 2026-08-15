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

    private final Map<String, Long> tokenUserMap = new ConcurrentHashMap<>();

    public String createToken(Long userId) {
        String token = UUID.randomUUID().toString().replace("-", "");
        tokenUserMap.put(token, userId);
        return token;
    }

    public Long getUserId(String token) {
        return tokenUserMap.get(token);
    }

    public void remove(String token) {
        tokenUserMap.remove(token);
    }
}
