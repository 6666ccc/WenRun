package com.wenrun.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/** 为每个 HTTP 请求创建或透传 requestId，并回写到响应头。 */
@Component
public class RequestTraceFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        String incoming = request.getHeader(RequestTrace.HEADER_NAME);
        String requestId = RequestTrace.isUsable(incoming) ? incoming : UUID.randomUUID().toString();
        long startedAt = System.currentTimeMillis();
        RequestTrace.set(requestId);
        response.setHeader(RequestTrace.HEADER_NAME, requestId);
        try {
            filterChain.doFilter(request, response);
        } finally {
            logger.info("http_request method=" + request.getMethod()
                    + " path=" + request.getRequestURI()
                    + " status=" + response.getStatus()
                    + " durationMs=" + (System.currentTimeMillis() - startedAt));
            RequestTrace.clear();
        }
    }
}
