package com.wenrun.dto;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 运动记录写入请求。时长必填，距离、热量、强度可空。
 */
@Data
public class ExerciseRecordDTO {

    private String exerciseType;
    private Integer durationMin;
    private BigDecimal distanceKm;
    private Integer caloriesKcal;
    private String intensity;
    private String sourceType;
    private LocalDateTime startedAt;
    private String remark;
}
