package com.wenrun.config;

import com.wenrun.util.ScheduleCutoffs;
import com.wenrun.util.ScheduleExpiry;
import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;

/**
 * 门诊排班窗口。上下午分界等时刻从 yml 读取，按北京时间计算。
 */
@Getter
@Setter
@ConfigurationProperties(prefix = "wenrun.clinic")
public class ClinicProperties {

    /** 业务时区 */
    private String timezone = "Asia/Shanghai";

    /**
     * 当天上午号源截止时间（含）。过了这个时刻不再展示/接受当天上午挂号。
     * YAML 中必须写成字符串，例如 {@code "12:00"}，否则 12:00 会被解析成数字。
     */
    private LocalTime morningEnd = LocalTime.NOON;

    /** 当天下午号源截止时间（含） */
    private LocalTime afternoonEnd = LocalTime.of(18, 0);

    /** 当天晚上号源截止时间（含） */
    private LocalTime eveningEnd = LocalTime.of(21, 0);

    /** 仅测试可替换；未设置时使用 timezone 对应系统时钟 */
    private Clock clock;

    public ZoneId zoneId() {
        return ZoneId.of(timezone);
    }

    public LocalDate today() {
        return LocalDate.now(clockOrSystem());
    }

    public LocalTime nowTime() {
        return LocalTime.now(clockOrSystem());
    }

    public ScheduleCutoffs cutoffs() {
        return new ScheduleCutoffs(morningEnd, afternoonEnd, eveningEnd);
    }

    public boolean isExpired(LocalDate workDate, String timePeriod) {
        return ScheduleExpiry.isExpired(workDate, timePeriod, today(), nowTime(), cutoffs());
    }

    private Clock clockOrSystem() {
        return clock != null ? clock : Clock.system(zoneId());
    }
}
