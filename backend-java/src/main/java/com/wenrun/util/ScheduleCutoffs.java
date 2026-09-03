package com.wenrun.util;

import java.time.LocalTime;

/**
 * 当天各就诊时段的截止时刻。过了对应时刻，该时段不再对患者展示、也不能再挂号。
 */
public record ScheduleCutoffs(LocalTime morningEnd, LocalTime afternoonEnd, LocalTime eveningEnd) {

    public static ScheduleCutoffs defaults() {
        return new ScheduleCutoffs(LocalTime.NOON, LocalTime.of(18, 0), LocalTime.of(21, 0));
    }
}
