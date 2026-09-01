package com.wenrun.ai.security;

/**
 * 当前请求的内部 Tool 身份。仅由 DelegatedToolAuthInterceptor 写入，并在请求结束时清理。
 */
public final class DelegatedToolContext {

    private static final ThreadLocal<DelegatedToolPrincipal> PRINCIPAL = new ThreadLocal<>();

    private DelegatedToolContext() {
    }

    public static void set(DelegatedToolPrincipal principal) {
        PRINCIPAL.set(principal);
    }

    public static DelegatedToolPrincipal getRequired() {
        DelegatedToolPrincipal principal = PRINCIPAL.get();
        if (principal == null) {
            throw new IllegalStateException("delegated tool principal is missing");
        }
        return principal;
    }

    public static void clear() {
        PRINCIPAL.remove();
    }
}
