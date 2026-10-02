package com.wenrun.ai.security;

import com.wenrun.common.ResultCode;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.SysRole;
import com.wenrun.entity.SysUser;
import com.wenrun.repository.SysUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;

/** 从当前 Java 登录会话和数据库角色签发限用途的知识库委托凭据。 */
@Service
@RequiredArgsConstructor
public class KnowledgeAccessService {

    public static final String MANAGE_SCOPE = "knowledge:manage";
    public static final String PUBLIC_SCOPE = "knowledge:public";
    public static final String STAFF_SCOPE = "knowledge:staff";

    private final SysUserRepository users;
    private final DelegationTokenService delegationTokens;

    public AccessContext requireAdministrator() {
        SysUser user = currentUser();
        Set<String> roles = roleCodes(user.getId());
        if (!roles.contains("admin")) {
            throw new BusinessException(ResultCode.FORBIDDEN, "仅知识库管理员可以管理资料");
        }
        return new AccessContext(
                user.getId(), accountType(user),
                delegationTokens.issue(user.getId(), accountType(user), null, Set.of(MANAGE_SCOPE)));
    }

    /**
     * 为来源读取签发最小权限令牌。患者只能读公开来源，医护可读公开和院内来源，
     * 管理员由数据库角色确认后可读待审核材料。scope 参数本身不授予权限。
     */
    public AccessContext sourceAccess(String requestedScope) {
        if (!"public".equals(requestedScope) && !"staff".equals(requestedScope)) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "资料范围无效");
        }
        SysUser user = currentUser();
        Set<String> roles = roleCodes(user.getId());
        Set<String> scopes = new LinkedHashSet<>();
        scopes.add(PUBLIC_SCOPE);
        if (roles.contains("admin")) {
            scopes.add(MANAGE_SCOPE);
            scopes.add(STAFF_SCOPE);
        } else if (AccountType.STAFF.equalsIgnoreCase(accountType(user)) && roles.contains("doctor")) {
            scopes.add(STAFF_SCOPE);
        }
        return new AccessContext(
                user.getId(), accountType(user),
                delegationTokens.issue(user.getId(), accountType(user), null, scopes));
    }

    private SysUser currentUser() {
        Long userId = UserContext.getUserId();
        SysUser user = userId == null ? null : users.selectById(userId);
        if (user == null || user.getStatus() == null || user.getStatus() != 1) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "登录已过期，请重新登录");
        }
        return user;
    }

    private Set<String> roleCodes(Long userId) {
        var roles = users.selectRolesByUserId(userId);
        if (roles == null || roles.isEmpty()) {
            return Set.of();
        }
        return roles.stream()
                .map(SysRole::getRoleCode)
                .filter(code -> code != null && !code.isBlank())
                .map(code -> code.trim().toLowerCase(Locale.ROOT))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }

    private String accountType(SysUser user) {
        return user.getAccountType() == null || user.getAccountType().isBlank()
                ? AccountType.INTERNAL : user.getAccountType();
    }

    public record AccessContext(Long userId, String accountType, String delegatedToken) { }
}
