package com.wenrun.common.context;

/**
 * 当前 OAuth 客户端上下文（client_credentials Token）
 */
public final class ClientContext {

    private static final ThreadLocal<String> CLIENT_ID = new ThreadLocal<>();
    private static final ThreadLocal<String> SCOPE = new ThreadLocal<>();

    private ClientContext() {
    }

    public static void set(String clientId, String scope) {
        CLIENT_ID.set(clientId);
        SCOPE.set(scope);
    }

    public static String getClientId() {
        return CLIENT_ID.get();
    }

    public static String getScope() {
        return SCOPE.get();
    }

    public static void clear() {
        CLIENT_ID.remove();
        SCOPE.remove();
    }
}
