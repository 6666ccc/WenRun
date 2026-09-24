package com.wenrun.vo;

import lombok.Data;

/**
 * 运动睡眠汇总。统计按时间窗，最近一条不受时间窗限制。
 */
@Data
public class ActivitySummaryVO {

    private Integer rangeDays;
    private Integer exerciseCount;
    private Integer exerciseMinutes;
    private Integer exerciseCalories;
    private Integer sleepCount;
    private Integer sleepAvgMinutes;
    private ExerciseRecordVO latestExercise;
    private SleepRecordVO latestSleep;
}
