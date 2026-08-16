package com.wenrun.ai.logging;

import java.util.regex.Pattern;

public final class AiLogSanitizer {

    private static final Pattern SENSITIVE = Pattern.compile(
            "(?i)\\b(authorization|x-delegated-token|x-api-key)\\b\\s*[:=]\\s*(?:bearer\\s+)?\\S+");
    private static final Pattern BEARER = Pattern.compile("(?i)\\bbearer\\s+\\S+");

    private AiLogSanitizer() {
    }

    public static String redact(String text) {
        if (text == null) {
            return null;
        }
        String value = SENSITIVE.matcher(text).replaceAll("$1=[redacted]");
        return BEARER.matcher(value).replaceAll("Bearer [redacted]");
    }
}
