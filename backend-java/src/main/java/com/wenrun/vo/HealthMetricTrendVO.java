package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 健康趋势查询结果。血压 records 中 primary/secondary 对应收缩压/舒张压。
 */
@Data
public class HealthMetricTrendVO {

    private String metricType;
    private String metricName;
    private String unit;
    private BigDecimal latestValue;
    private BigDecimal latestSecondaryValue;
    private List<HealthMetricPointVO> records = new ArrayList<>();
}
