package com.wenrun.vo;

import lombok.Data;

/**
 * 可供趋势图切换的指标
 */
@Data
public class HealthMetricTypeVO {

    private String metricType;
    private String metricName;
    private String unit;
    private Boolean dualLine;
    private Boolean derived;
}
