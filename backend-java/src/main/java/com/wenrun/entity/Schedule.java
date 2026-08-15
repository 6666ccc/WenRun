package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

@Data
public class Schedule {
    private Long id;
    private Long deptId;
    private Long staffId;
    private LocalDate workDate;
    private String timePeriod;
    private Integer totalCount;
    private Integer remainingCount;
    private BigDecimal registerFee;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
