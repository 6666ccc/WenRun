package com.wenrun.enums;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 健康指标类型。数据库只存英文 code，中文名和单位由枚举固定。
 * BMI 仅用于趋势查询，不写入 health_metric_record。
 */
public enum HealthMetricType {

    WEIGHT("体重", "kg", true, false),
    WAIST("腰围", "cm", true, false),
    BLOOD_PRESSURE("血压", "mmHg", true, true),
    BLOOD_GLUCOSE("血糖", "mmol/L", true, false),
    HEART_RATE("心率", "次/分", true, false),
    SPO2("血氧", "%", true, false),
    TEMPERATURE("体温", "℃", true, false),
    RESPIRATORY_RATE("呼吸频率", "次/分", true, false),
    BMI("BMI", "kg/m²", false, false);

    private final String displayName;
    private final String unit;
    private final boolean persisted;
    private final boolean dualLine;

    HealthMetricType(String displayName, String unit, boolean persisted, boolean dualLine) {
        this.displayName = displayName;
        this.unit = unit;
        this.persisted = persisted;
        this.dualLine = dualLine;
    }

    public String getCode() {
        return name();
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getUnit() {
        return unit;
    }

    /** false 表示虚拟指标，不能写入 health_metric_record */
    public boolean isPersisted() {
        return persisted;
    }

    /** 血压等需要两条折线 */
    public boolean isDualLine() {
        return dualLine;
    }

    public static Optional<HealthMetricType> fromCode(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        String normalized = code.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(type -> type.name().equals(normalized))
                .findFirst();
    }
}
