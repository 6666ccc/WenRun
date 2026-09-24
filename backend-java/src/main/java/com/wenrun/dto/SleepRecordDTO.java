package com.wenrun.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 睡眠记录写入请求。时长由入睡与醒来时间计算，不接收客户端时长。
 */
@Data
public class SleepRecordDTO {

    private LocalDateTime bedtime;
    private LocalDateTime wakeTime;
    private Integer quality;
    private String sourceType;
    private String remark;
}
