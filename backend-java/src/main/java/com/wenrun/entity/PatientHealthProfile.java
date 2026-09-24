package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 患者健康档案当前值，对应表 patient_health_profile
 */
@Data
public class PatientHealthProfile {

    private Long id;
    private Long patientId;
    private BigDecimal heightCm;
    private BigDecimal weightKg;
    private BigDecimal waistCm;
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
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
