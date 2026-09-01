package com.wenrun.config;

/**
 * 登录 Session 存储。内存与 Redis 实现共用此接口，避免调用方绑定具体后端。
 */
public interface TokenSessionStore {

    default String createToken(Long userId) {
        return createToken(userId, null);
    }

    String createToken(Long userId, String accountType);

    Long getUserId(String token);

    String getAccountType(String token);

    void remove(String token);
}
