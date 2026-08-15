package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class MedicalItem {
    private Long id;
    private String itemCode;
    private String itemName;
    private Integer itemType;
    private BigDecimal price;
    private Long deptId;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
