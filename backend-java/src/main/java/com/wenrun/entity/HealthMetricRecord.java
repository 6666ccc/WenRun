package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 健康指标纵向记录，对应表 health_metric_record。
 * patient_id 是医疗主体；created_by_user_id 是录入人。
 */
@Data
public class HealthMetricRecord {

    private Long id;
    private Long patientId;
    private String metricType;
    private BigDecimal primaryValue;
    private BigDecimal secondaryValue;
    private String measureContext;
    private String sourceType;
    private LocalDateTime measuredAt;
    private Long createdByUserId;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private Integer isDeleted;
}
