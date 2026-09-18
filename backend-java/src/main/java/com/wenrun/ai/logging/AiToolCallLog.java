package com.wenrun.ai.logging;

import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.config.RequestTrace;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.util.StringUtils;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Agent 调用 Java 内部 Tool API 时的访问日志拼装。
 * 只记录工具名、入参和返回体，不记录令牌。
 */
public final class AiToolCallLog {

    public static final String PRINCIPAL_ATTR = DelegatedToolPrincipal.class.getName();
    static final ZoneId CLINIC_ZONE = ZoneId.of("Asia/Shanghai");
    static final int MAX_PAYLOAD_CHARS = 2_000;
    private static final String TOOL_PREFIX = "/api/internal/ai-tools";
    private static final DateTimeFormatter TIME_FORMAT = DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    private AiToolCallLog() {
    }

    public static String now() {
        return ZonedDateTime.now(CLINIC_ZONE).format(TIME_FORMAT);
    }

    public static String resolveTool(String method, String path) {
        String verb = method == null ? "" : method.toUpperCase();
        String suffix = normalizePath(path);
        if (suffix.isEmpty()) {
            return verb + " " + path;
        }
        String[] parts = suffix.split("/");
        if ("GET".equals(verb) && parts.length == 1 && "departments".equals(parts[0])) {
            return "list_departments";
        }
        if ("GET".equals(verb) && parts.length == 2 && "departments".equals(parts[0])) {
            return "get_department";
        }
        if ("GET".equals(verb) && parts.length == 1 && "schedules".equals(parts[0])) {
            return "list_schedules";
        }
        if ("GET".equals(verb) && parts.length == 2 && "schedules".equals(parts[0])) {
            return "get_schedule";
        }
        if ("GET".equals(verb) && parts.length == 1 && "staff".equals(parts[0])) {
            return "list_doctors";
        }
        if ("GET".equals(verb) && parts.length == 2 && "staff".equals(parts[0])) {
            return "get_staff";
        }
        if ("GET".equals(verb) && parts.length == 1 && "registrations".equals(parts[0])) {
            return "list_my_registrations";
        }
        if ("GET".equals(verb) && parts.length == 2 && "registrations".equals(parts[0])
                && "pending".equals(parts[1])) {
            return "list_my_pending_registrations";
        }
        if ("POST".equals(verb) && parts.length == 1 && "registrations".equals(parts[0])) {
            return "create_registration";
        }
        if ("POST".equals(verb) && parts.length == 3 && "registrations".equals(parts[0])
                && "cancel".equals(parts[2])) {
            return "cancel_registration";
        }
        if ("GET".equals(verb) && parts.length == 1 && "memories".equals(parts[0])) {
            return "list_memories";
        }
        if ("POST".equals(verb) && parts.length == 1 && "memories".equals(parts[0])) {
            return "remember_preference";
        }
        if ("DELETE".equals(verb) && parts.length == 2 && "memories".equals(parts[0])) {
            return "forget_preference";
        }
        return verb + " " + suffix;
    }

    public static String truncate(String value) {
        if (!StringUtils.hasText(value)) {
            return "";
        }
        String compact = value.replaceAll("\\s+", " ").trim();
        if (compact.length() <= MAX_PAYLOAD_CHARS) {
            return compact;
        }
        return compact.substring(0, MAX_PAYLOAD_CHARS) + "...[truncated]";
    }

    public static String queryParams(HttpServletRequest request) {
        Map<String, String[]> raw = request.getParameterMap();
        if (raw == null || raw.isEmpty()) {
            return "";
        }
        Map<String, String> compact = new LinkedHashMap<>();
        raw.forEach((key, values) -> {
            if (!StringUtils.hasText(key) || isSensitive(key)) {
                return;
            }
            compact.put(key, values == null || values.length == 0 ? "" : String.join(",", values));
        });
        return compact.toString();
    }

    public static String decodeBody(byte[] body, String encoding) {
        if (body == null || body.length == 0) {
            return "";
        }
        Charset charset = StandardCharsets.UTF_8;
        if (StringUtils.hasText(encoding)) {
            try {
                charset = Charset.forName(encoding);
            } catch (Exception ignored) {
                charset = StandardCharsets.UTF_8;
            }
        }
        return truncate(new String(body, charset));
    }

    public static String requestId(HttpServletRequest request) {
        String current = RequestTrace.get();
        if (RequestTrace.isUsable(current)) {
            return current;
        }
        String header = request.getHeader(RequestTrace.HEADER_NAME);
        return RequestTrace.isUsable(header) ? header : "";
    }

    public static String identity(HttpServletRequest request) {
        Object value = request.getAttribute(PRINCIPAL_ATTR);
        if (!(value instanceof DelegatedToolPrincipal principal)) {
            return "userId=- patientId=-";
        }
        return "userId=" + principal.userId() + " patientId=" + principal.patientId();
    }

    public static String params(String pathVariables, String query, String body) {
        StringBuilder builder = new StringBuilder();
        appendPart(builder, "path", pathVariables);
        appendPart(builder, "query", query);
        appendPart(builder, "body", body);
        return builder.isEmpty() ? "-" : builder.toString();
    }

    public static String pathSuffix(String path) {
        return normalizePath(path);
    }

    private static void appendPart(StringBuilder builder, String label, String value) {
        if (!StringUtils.hasText(value)) {
            return;
        }
        if (!builder.isEmpty()) {
            builder.append(' ');
        }
        builder.append(label).append('=').append(truncate(value));
    }

    private static boolean isSensitive(String key) {
        String normalized = key.toLowerCase();
        return normalized.contains("token")
                || normalized.contains("authorization")
                || normalized.contains("password")
                || normalized.contains("secret");
    }

    private static String normalizePath(String path) {
        if (!StringUtils.hasText(path)) {
            return "";
        }
        String value = path;
        int query = value.indexOf('?');
        if (query >= 0) {
            value = value.substring(0, query);
        }
        if (value.startsWith(TOOL_PREFIX)) {
            value = value.substring(TOOL_PREFIX.length());
        }
        while (value.startsWith("/")) {
            value = value.substring(1);
        }
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }
}
