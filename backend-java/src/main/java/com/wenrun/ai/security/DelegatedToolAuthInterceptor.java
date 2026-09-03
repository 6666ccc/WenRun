package com.wenrun.ai.security;

import com.wenrun.common.ResultCode;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

/** 仅认证 Python 代理进入 Java 内部 Tool API 的短期委托 JWT。 */
@Component
@RequiredArgsConstructor
public class DelegatedToolAuthInterceptor implements HandlerInterceptor {

    private final DelegationTokenService delegationTokenService;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String token = resolveBearerToken(request);
        if (!StringUtils.hasText(token)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "缺少 AI 委托令牌");
        }
        DelegatedToolPrincipal principal = delegationTokenService.verifyForToolApi(token);
        DelegatedToolContext.set(principal);
        // 业务 Service 的「患者本人」校验读的是 UserContext，而这条路径不走 AuthInterceptor。
        // 不补这两行，退号的归属校验会整段失效，操作人字段也会写成 null。
        UserContext.setUserId(principal.userId());
        UserContext.setAccountType(principal.accountType());
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        DelegatedToolContext.clear();
        UserContext.clear();
    }

    private String resolveBearerToken(HttpServletRequest request) {
        String authorization = request.getHeader("Authorization");
        if (StringUtils.hasText(authorization) && authorization.startsWith("Bearer ")) {
            return authorization.substring(7);
        }
        return null;
    }
}
