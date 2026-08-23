package com.wenrun.config;

import org.slf4j.MDC;
import org.springframework.util.StringUtils;

/**
 * 保存当前请求的追踪号，供日志和 Java 调 Python 调用共同使用。
 *
 * <p>追踪号不是用户身份信息，不能替代登录 Token。</p>
 */
public final class RequestTrace {

    public static final String HEADER_NAME = "X-Request-Id";
    public static final String MDC_KEY = "requestId";
    private static final ThreadLocal<String> REQUEST_ID = new ThreadLocal<>();

    private RequestTrace() {
    }

    public static void set(String requestId) {
        REQUEST_ID.set(requestId);
        MDC.put(MDC_KEY, requestId);
    }

    public static String get() {
        return REQUEST_ID.get();
    }

    public static void clear() {
        REQUEST_ID.remove();
        MDC.remove(MDC_KEY);
    }

    public static void runWith(String requestId, Runnable action) {
        if (isUsable(requestId)) {
            set(requestId);
        } else {
            clear();
        }
        try {
            action.run();
        } finally {
            clear();
        }
    }

    /** 只接受长度合理的外部追踪号，避免把过长请求头写入日志。 */
    public static boolean isUsable(String requestId) {
        if (!StringUtils.hasText(requestId) || requestId.length() > 64) {
            return false;
        }
        for (int index = 0; index < requestId.length(); index++) {
            if (Character.isISOControl(requestId.charAt(index))) {
                return false;
            }
        }
        return true;
    }
}
