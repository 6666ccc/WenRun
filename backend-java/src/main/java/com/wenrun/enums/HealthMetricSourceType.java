package com.wenrun.enums;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 健康指标数据来源。数据库存英文 code。
 */
public enum HealthMetricSourceType {

    MANUAL("用户手动填写"),
    DEVICE("医疗设备或可穿戴设备同步"),
    HOSPITAL("医院系统同步"),
    REPORT("从检查报告中获取"),
    AI_EXTRACT("由 AI/Agent 从医疗文档中提取");

    private final String displayName;

    HealthMetricSourceType(String displayName) {
        this.displayName = displayName;
    }

    public String getCode() {
        return name();
    }

    public String getDisplayName() {
        return displayName;
    }

    public static Optional<HealthMetricSourceType> fromCode(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        String normalized = code.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(type -> type.name().equals(normalized))
                .findFirst();
    }
}
