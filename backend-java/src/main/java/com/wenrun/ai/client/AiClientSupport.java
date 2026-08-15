package com.wenrun.ai.client;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * AI 客户端公共工具。
 */
final class AiClientSupport {

    private AiClientSupport() {
    }

    static String readBody(InputStream body) {
        if (body == null) {
            return "";
        }
        try (body) {
            return new String(body.readAllBytes(), StandardCharsets.UTF_8).trim();
        } catch (Exception ex) {
            return "";
        }
    }
}
