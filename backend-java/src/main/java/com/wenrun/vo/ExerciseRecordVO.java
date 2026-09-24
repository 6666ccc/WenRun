package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 运动记录
 */
@Data
public class ExerciseRecordVO {

    private Long id;
    private String exerciseType;
    private String exerciseName;
    private Integer durationMin;
    private BigDecimal distanceKm;
    private Integer caloriesKcal;
    private String intensity;
    private String intensityName;
    private String sourceType;
    private LocalDateTime startedAt;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
