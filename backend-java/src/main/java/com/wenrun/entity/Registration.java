package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class Registration {
    private Long id;
    private String regNo;
    private Long patientId;
    private Long scheduleId;
    private Long deptId;
    private Long staffId;
    private LocalDateTime regTime;
    private BigDecimal regFee;
    private Integer status;
    private Long cashierId;
    private Long registrantUserId;
    private String idempotencyKey;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
