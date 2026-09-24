package com.wenrun.enums;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 运动类型。数据库只存英文 code。
 */
public enum ExerciseType {

    WALK("步行"),
    RUN("跑步"),
    CYCLE("骑行"),
    SWIM("游泳"),
    STRENGTH("力量训练"),
    YOGA("瑜伽"),
    BALL("球类"),
    OTHER("其他");

    private final String displayName;

    ExerciseType(String displayName) {
        this.displayName = displayName;
    }

    public String getCode() {
        return name();
    }

    public String getDisplayName() {
        return displayName;
    }

    public static Optional<ExerciseType> fromCode(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        String normalized = code.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(type -> type.name().equals(normalized))
                .findFirst();
    }
}
