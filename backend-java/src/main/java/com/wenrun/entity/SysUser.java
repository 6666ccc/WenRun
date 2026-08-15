package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SysUser {
    private Long id;
    private String username;
    private String password;
    private String realName;
    private String phone;
    /** 0未验证 1已验证 */
    private Integer phoneVerified;
    /** internal院内 staff医护 patient患者 */
    private String accountType;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
