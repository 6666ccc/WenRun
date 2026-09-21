package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 健康档案当前值
 */
@Data
public class HealthProfileVO {

    private Long id;
    private Long patientId;
    private Boolean exists;
    private BigDecimal heightCm;
    private BigDecimal weightKg;
    private Integer systolicMmhg;
    private Integer diastolicMmhg;
    private BigDecimal glucoseMmol;
    private String glucoseType;
    private Integer heartRateBpm;
    private Integer spo2Pct;
    private Integer respiratoryRateBpm;
    private BigDecimal temperatureC;
    private LocalDateTime measuredAt;
    private String pastHistory;
    private String familyHistory;
    private String personalHistory;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
