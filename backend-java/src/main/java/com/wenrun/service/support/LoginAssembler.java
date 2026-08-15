package com.wenrun.service.support;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.constant.PortalType;
import com.wenrun.entity.SysRole;
import com.wenrun.entity.SysUser;
import org.springframework.util.StringUtils;

import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * 登录门户与主角色解析
 */
public final class LoginAssembler {

    private static final Map<String, Integer> ROLE_PRIORITY = Map.of(
            "patient", 0,
            "doctor", 1,
            "admin", 2,
            "cashier", 3,
            "pharmacist", 4
    );

    private static final Map<String, String> ROLE_PORTAL_FALLBACK = Map.of(
            "doctor", PortalType.DOCTOR,
            "patient", PortalType.PATIENT,
            "admin", PortalType.ADMIN,
            "cashier", PortalType.ADMIN,
            "pharmacist", PortalType.ADMIN
    );

    private LoginAssembler() {
    }

    public static SysRole pickPrimaryRole(List<SysRole> roles) {
        if (roles == null || roles.isEmpty()) {
            return null;
        }
        return roles.stream()
                .min(Comparator.comparingInt(r -> ROLE_PRIORITY.getOrDefault(
                        normalizeCode(r.getRoleCode()), Integer.MAX_VALUE)))
                .orElse(roles.get(0));
    }

    public static String resolvePortalType(SysUser user, SysRole primaryRole) {
        String accountType = user != null ? user.getAccountType() : null;
        if (AccountType.PATIENT.equals(accountType)) {
            return PortalType.PATIENT;
        }
        if (AccountType.STAFF.equals(accountType)) {
            return PortalType.DOCTOR;
        }
        if (primaryRole != null && StringUtils.hasText(primaryRole.getDefaultPortal())) {
            return primaryRole.getDefaultPortal();
        }
        if (primaryRole != null && StringUtils.hasText(primaryRole.getRoleCode())) {
            String portal = ROLE_PORTAL_FALLBACK.get(normalizeCode(primaryRole.getRoleCode()));
            if (portal != null) {
                return portal;
            }
        }
        return PortalType.ADMIN;
    }

    private static String normalizeCode(String roleCode) {
        return roleCode == null ? "" : roleCode.trim().toLowerCase();
    }
}
