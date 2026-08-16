package com.wenrun.ai.tools.interceptor;

import com.wenrun.ai.delegation.AiDelegationClaims;
import com.wenrun.ai.delegation.AiDelegationException;
import com.wenrun.ai.delegation.AiDelegationTokenService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
@RequiredArgsConstructor
public class DelegatedJwtInterceptor implements HandlerInterceptor {

    public static final String CLAIMS_ATTR = "AI_DELEGATION_CLAIMS";

    private final AiDelegationTokenService tokenService;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String token = resolveBearer(request);
        AiDelegationClaims claims = tokenService.verify(token);
        request.setAttribute(CLAIMS_ATTR, claims);
        return true;
    }

    public static AiDelegationClaims claimsFrom(HttpServletRequest request) {
        Object value = request.getAttribute(CLAIMS_ATTR);
        if (value instanceof AiDelegationClaims claims) {
            return claims;
        }
        throw new AiDelegationException("missing delegation claims");
    }

    private static String resolveBearer(HttpServletRequest request) {
        String auth = request.getHeader("Authorization");
        if (StringUtils.hasText(auth) && auth.startsWith("Bearer ")) {
            return auth.substring(7);
        }
        throw new AiDelegationException("missing delegation token");
    }
}
