package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 健康趋势图上的一个点
 */
@Data
public class HealthMetricPointVO {

    private BigDecimal primaryValue;
    private BigDecimal secondaryValue;
    private String measureContext;
    private LocalDateTime measuredAt;
}
