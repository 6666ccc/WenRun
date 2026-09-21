package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 健康指标单条记录
 */
@Data
public class HealthMetricRecordVO {

    private Long id;
    private String metricType;
    private String metricName;
    private String unit;
    private BigDecimal primaryValue;
    private BigDecimal secondaryValue;
    private String measureContext;
    private String sourceType;
    private LocalDateTime measuredAt;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
