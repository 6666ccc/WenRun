package com.wenrun.dto;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 健康指标写入请求
 */
@Data
public class HealthMetricRecordDTO {

    private String metricType;
    private BigDecimal primaryValue;
    private BigDecimal secondaryValue;
    private String measureContext;
    private String sourceType;
    private LocalDateTime measuredAt;
    private String remark;
}
