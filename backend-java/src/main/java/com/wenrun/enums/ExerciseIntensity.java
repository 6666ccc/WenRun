package com.wenrun.enums;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 运动强度。可空；数据库只存英文 code。
 */
public enum ExerciseIntensity {

    LOW("轻松"),
    MODERATE("中等"),
    HIGH("剧烈");

    private final String displayName;

    ExerciseIntensity(String displayName) {
        this.displayName = displayName;
    }

    public String getCode() {
        return name();
    }

    public String getDisplayName() {
        return displayName;
    }

    public static Optional<ExerciseIntensity> fromCode(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        String normalized = code.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(type -> type.name().equals(normalized))
                .findFirst();
    }
}
