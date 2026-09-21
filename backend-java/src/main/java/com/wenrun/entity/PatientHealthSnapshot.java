package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 患者健康档案历史快照，对应表 patient_health_snapshot
 */
@Data
public class PatientHealthSnapshot {

    private Long id;
    private Long patientId;
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
}
