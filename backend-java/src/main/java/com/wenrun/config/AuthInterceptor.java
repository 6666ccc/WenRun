package com.wenrun.config;

import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.common.ResultCode;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
@RequiredArgsConstructor
public class AuthInterceptor implements HandlerInterceptor {

    private final AuthTokenStore authTokenStore;
    private final AiServiceProperties aiServiceProperties;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }

        String apiKey = request.getHeader("X-Api-Key");
        String configuredApiKey = aiServiceProperties.getApiKey();
        if (StringUtils.hasText(apiKey)
                && StringUtils.hasText(configuredApiKey)
                && apiKey.equals(configuredApiKey)) {
            String userIdHeader = request.getHeader("X-User-Id");
            if (StringUtils.hasText(userIdHeader)) {
                UserContext.setUserId(Long.parseLong(userIdHeader));
            }
            return true;
        }

        String token = resolveToken(request);
        if (!StringUtils.hasText(token)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "未登录或 Token 无效");
        }
        Long userId = authTokenStore.getUserId(token);
        if (userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "登录已过期，请重新登录");
        }
        UserContext.setUserId(userId);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        UserContext.clear();
    }

    private String resolveToken(HttpServletRequest request) {
        String auth = request.getHeader("Authorization");
        if (StringUtils.hasText(auth) && auth.startsWith("Bearer ")) {
            return auth.substring(7);
        }
        return request.getHeader("X-Token");
    }
}
