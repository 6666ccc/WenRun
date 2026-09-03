package com.wenrun.util;

import java.time.LocalDate;
import java.time.LocalTime;

/**
 * 判断排班/挂号是否已过就诊时间。
 */
public final class ScheduleExpiry {

    private ScheduleExpiry() {
    }

    public static boolean isExpired(LocalDate workDate, String timePeriod, LocalDate today, LocalTime nowTime) {
        return isExpired(workDate, timePeriod, today, nowTime, ScheduleCutoffs.defaults());
    }

    public static boolean isExpired(LocalDate workDate, String timePeriod, LocalDate today, LocalTime nowTime,
                                    ScheduleCutoffs cutoffs) {
        if (workDate == null || today == null || cutoffs == null) {
            return false;
        }
        if (workDate.isBefore(today)) {
            return true;
        }
        if (workDate.isAfter(today)) {
            return false;
        }
        if (timePeriod == null || nowTime == null) {
            return false;
        }
        LocalTime end = switch (timePeriod) {
            case "上午" -> cutoffs.morningEnd();
            case "下午" -> cutoffs.afternoonEnd();
            case "晚上" -> cutoffs.eveningEnd();
            default -> null;
        };
        if (end == null) {
            return false;
        }
        return !nowTime.isBefore(end);
    }
}
