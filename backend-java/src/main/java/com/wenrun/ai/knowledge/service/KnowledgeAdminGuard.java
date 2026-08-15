package com.wenrun.ai.knowledge.service;

import com.wenrun.common.ResultCode;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.SysRole;
import com.wenrun.repository.SysUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class KnowledgeAdminGuard {

    private final SysUserRepository userMapper;

    public void requireAdmin() {
        Long userId = currentUserId();
        List<SysRole> roles = userMapper.selectRolesByUserId(userId);
        boolean admin = roles != null && roles.stream()
                .anyMatch(role -> "admin".equals(role.getRoleCode()));
        if (!admin) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅管理员可管理知识库");
        }
    }

    public Long currentUserId() {
        Long userId = UserContext.getUserId();
        if (userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "未登录或登录状态已失效");
        }
        return userId;
    }
}
