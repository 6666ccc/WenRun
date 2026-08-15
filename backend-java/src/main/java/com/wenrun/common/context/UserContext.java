package com.wenrun.common.context;

/**
 * 当前登录用户上下文
 */
public final class UserContext {

    private static final ThreadLocal<Long> USER_ID = new ThreadLocal<>();
    private static final ThreadLocal<String> ACCOUNT_TYPE = new ThreadLocal<>();

    private UserContext() {
    }

    public static void setUserId(Long userId) {
        USER_ID.set(userId);
    }

    public static Long getUserId() {
        return USER_ID.get();
    }

    public static void setAccountType(String accountType) {
        ACCOUNT_TYPE.set(accountType);
    }

    public static String getAccountType() {
        return ACCOUNT_TYPE.get();
    }

    public static void clear() {
        USER_ID.remove();
        ACCOUNT_TYPE.remove();
    }
}
