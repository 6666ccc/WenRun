package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.UpdateProfileDTO;
import com.wenrun.service.AuthService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

/**
 * 个人中心 — 用户资料管理
 */
@RestController
@RequestMapping("/api/user")
@RequiredArgsConstructor
public class UserController {

    private final AuthService authService;

    /**
     * PUT /api/user/profile — 更新个人资料（真实姓名、电话等）
     */
    @PutMapping("/profile")
    public Result<Void> updateProfile(@RequestBody UpdateProfileDTO dto,
                                      HttpServletRequest request) {
        Long userId = resolveUserId(request);
        authService.updateProfile(userId, dto);
        return Result.success();
    }

    /** 从请求头解析 Token 并获取当前用户 ID */
    private Long resolveUserId(HttpServletRequest request) {
        String auth = request.getHeader("Authorization");
        if (StringUtils.hasText(auth) && auth.startsWith("Bearer ")) {
            String token = auth.substring(7);
            return authService.resolveUserId(token);
        }
        String token = request.getHeader("X-Token");
        if (StringUtils.hasText(token)) {
            return authService.resolveUserId(token);
        }
        throw new com.wenrun.common.exception.BusinessException("未登录");
    }
}
