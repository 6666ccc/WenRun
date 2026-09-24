package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 患者睡眠记录，对应表 patient_sleep_record。
 */
@Data
public class PatientSleepRecord {

    private Long id;
    private Long patientId;
    private LocalDateTime bedtime;
    private LocalDateTime wakeTime;
    private Integer durationMin;
    private Integer quality;
    private String sourceType;
    private Long createdByUserId;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private Integer isDeleted;
}
