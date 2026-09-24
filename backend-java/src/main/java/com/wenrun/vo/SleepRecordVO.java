package com.wenrun.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 睡眠记录
 */
@Data
public class SleepRecordVO {

    private Long id;
    private LocalDateTime bedtime;
    private LocalDateTime wakeTime;
    private Integer durationMin;
    private Integer quality;
    private String qualityName;
    private String sourceType;
    private String remark;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
