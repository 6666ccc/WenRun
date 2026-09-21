package com.wenrun.dto;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 健康档案写入请求
 */
@Data
public class HealthProfileDTO {

    private BigDecimal heightCm;
    private BigDecimal weightKg;
    private Integer systolicMmhg;
    private Integer diastolicMmhg;
    private BigDecimal glucoseMmol;
    /** fasting空腹 / random随机 / postprandial餐后 */
    private String glucoseType;
    private Integer heartRateBpm;
    private Integer spo2Pct;
    private Integer respiratoryRateBpm;
    private BigDecimal temperatureC;
    private LocalDateTime measuredAt;
    private String pastHistory;
    private String familyHistory;
    private String personalHistory;
}
