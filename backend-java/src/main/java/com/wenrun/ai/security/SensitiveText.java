package com.wenrun.ai.security;

import java.util.regex.Pattern;

/**
 * 模型上下文和工具日志共用的脱敏。只去掉身份证件、手机号、住址片段和文件地址。
 */
public final class SensitiveText {

    private static final Pattern SECRET = Pattern.compile(
            "(?i)https?://\\S+|cos://\\S+|(?<!\\d)\\d{17}[0-9Xx](?!\\d)|(?<!\\d)1[3-9]\\d{9}(?!\\d)");
    private static final Pattern ADDRESS = Pattern.compile(
            "[\\u4e00-\\u9fff]{1,12}(?:省|市).{0,40}(?:路|街|巷|道|号|室)");

    private SensitiveText() {
    }

    public static String redact(String value) {
        if (value == null || value.isEmpty()) {
            return value;
        }
        String text = SECRET.matcher(value).replaceAll("[已省略]");
        return ADDRESS.matcher(text).replaceAll("[已省略]");
    }

    public static String cleanOrNull(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        String cleaned = redact(value).trim();
        if (cleaned.isEmpty() || cleaned.replace("[已省略]", "").isBlank()) {
            return null;
        }
        return cleaned;
    }
}
