package com.wenrun.vo;

import lombok.Data;

@Data
public class StaffVO {
    private Long id;
    private String staffNo;
    private String name;
    private Long deptId;
    private String deptName;
    private String title;
    private Long userId;
    private Integer status;
}
