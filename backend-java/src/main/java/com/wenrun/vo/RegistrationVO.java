package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;



@Data
public class RegistrationVO {
    private Long id;
    private String regNo;
    private Long patientId;
    private String patientName;
    private Long scheduleId;
    private Long deptId;
    private String deptName;
    private Long staffId;
    private String staffName;
    /** 就诊日期（来自排班 schedule.work_date） */
    private LocalDate workDate;
    /** 就诊时段：上午/下午/晚上（来自排班 schedule.time_period） */
    private String timePeriod;
    private LocalDateTime regTime;
    private BigDecimal regFee;
    private Integer status;
    private Long registrantUserId;
    private String registrantUserName;
}
