package com.wenrun.ai.logging;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import org.springframework.web.util.ContentCachingRequestWrapper;
import org.springframework.web.util.ContentCachingResponseWrapper;

import java.io.IOException;

/**
 * 记录 Python Agent 每次打到 Java 内部 Tool API 的入参与返回。
 * 放在 {@code RequestTraceFilter} 之内，这样日志里能带上同一条 requestId。
 */
@Slf4j
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 20)
public class AiToolAccessFilter extends OncePerRequestFilter {

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        return path == null || !path.contains("/api/internal/ai-tools");
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        ContentCachingRequestWrapper cachedRequest = wrapRequest(request);
        ContentCachingResponseWrapper cachedResponse = wrapResponse(response);
        long startedAt = System.currentTimeMillis();
        String at = AiToolCallLog.now();
        try {
            filterChain.doFilter(cachedRequest, cachedResponse);
        } finally {
            logCall(cachedRequest, cachedResponse, at, startedAt);
            cachedResponse.copyBodyToResponse();
        }
    }

    private void logCall(
            ContentCachingRequestWrapper request,
            ContentCachingResponseWrapper response,
            String at,
            long startedAt
    ) {
        String tool = AiToolCallLog.resolveTool(request.getMethod(), request.getRequestURI());
        String params = AiToolCallLog.params(
                AiToolCallLog.pathSuffix(request.getRequestURI()),
                AiToolCallLog.queryParams(request),
                AiToolCallLog.decodeBody(request.getContentAsByteArray(), request.getCharacterEncoding()));
        String result = AiToolCallLog.decodeBody(
                response.getContentAsByteArray(), response.getCharacterEncoding());
        long durationMs = System.currentTimeMillis() - startedAt;
        String message = "ai_tool at={} requestId={} {} tool={} params={} result={} status={} durationMs={}";
        Object[] args = {
                at,
                AiToolCallLog.requestId(request),
                AiToolCallLog.identity(request),
                tool,
                params,
                result.isEmpty() ? "-" : result,
                response.getStatus(),
                durationMs
        };
        if (response.getStatus() >= 400) {
            log.warn(message, args);
        } else {
            log.info(message, args);
        }
    }

    private ContentCachingRequestWrapper wrapRequest(HttpServletRequest request) {
        if (request instanceof ContentCachingRequestWrapper wrapped) {
            return wrapped;
        }
        return new ContentCachingRequestWrapper(request);
    }

    private ContentCachingResponseWrapper wrapResponse(HttpServletResponse response) {
        if (response instanceof ContentCachingResponseWrapper wrapped) {
            return wrapped;
        }
        return new ContentCachingResponseWrapper(response);
    }
}
