package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;

@Data
public class ScheduleVO {
    private Long id;
    private Long deptId;
    private String deptName;
    private Long staffId;
    private String staffName;
    private LocalDate workDate;
    private String timePeriod;
    private Integer totalCount;
    private Integer remainingCount;
    private BigDecimal registerFee;
}
