package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SysRole {
    private Long id;
    private String roleCode;
    private String roleName;
    /** admin / doctor / patient */
    private String defaultPortal;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
