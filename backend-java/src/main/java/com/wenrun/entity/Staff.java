package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class Staff {
    private Long id;
    private String staffNo;
    private String name;
    private Long deptId;
    private String title;
    private Long userId;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
