package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 患者运动记录，对应表 patient_exercise_record。
 */
@Data
public class PatientExerciseRecord {

    private Long id;
    private Long patientId;
    private String exerciseType;
    private Integer durationMin;
    private BigDecimal distanceKm;
    private Integer caloriesKcal;
    private String intensity;
    private String sourceType;
    private LocalDateTime startedAt;
    private Long createdByUserId;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private Integer isDeleted;
}
