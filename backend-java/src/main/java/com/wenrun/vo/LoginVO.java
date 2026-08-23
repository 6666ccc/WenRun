package com.wenrun.vo;

import lombok.Data;

import java.util.List;

@Data
public class LoginVO {
    private String token;
    private Long userId;
    private String username;
    private String realName;
    /** 主角色编码（与 sys_role.role_code 一致，小写） */
    private String roleCode;
    private String roleName;
    /** 前端门户：admin / doctor / patient */
    private String portalType;
    /** 与 portalType 相同，兼容前端 userType 字段 */
    private String userType;
    /** 医生端业务 ID */
    private Long staffId;
    /** 患者端业务 ID */
    private Long patientId;
    /** 全部角色编码 */
    private List<String> roles;
}
