package com.wenrun.enums;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 血糖测量场景。仅 BLOOD_GLUCOSE 使用，数据库存英文 code。
 */
public enum GlucoseMeasureContext {

    FASTING("空腹"),
    BEFORE_MEAL("餐前"),
    AFTER_MEAL_1H("餐后1小时"),
    AFTER_MEAL_2H("餐后2小时"),
    RANDOM("随机");

    private final String displayName;

    GlucoseMeasureContext(String displayName) {
        this.displayName = displayName;
    }

    public String getCode() {
        return name();
    }

    public String getDisplayName() {
        return displayName;
    }

    public static Optional<GlucoseMeasureContext> fromCode(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        String normalized = code.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(type -> type.name().equals(normalized))
                .findFirst();
    }
}
