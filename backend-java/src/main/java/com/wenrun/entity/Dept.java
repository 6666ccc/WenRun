package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class Dept {
    private Long id;
    private String deptCode;
    private String deptName;
    private Long parentId;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
