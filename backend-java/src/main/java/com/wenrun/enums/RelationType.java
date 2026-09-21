package com.wenrun.enums;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 账号与患者的关系类型。数据库只存英文 code。
 */
public enum RelationType {

    SELF("本人"),
    SPOUSE("配偶"),
    CHILD("子女"),
    PARENT("父母"),
    OTHER("其他家庭成员");

    private final String displayName;

    RelationType(String displayName) {
        this.displayName = displayName;
    }

    public String getCode() {
        return name();
    }

    public String getDisplayName() {
        return displayName;
    }

    public static Optional<RelationType> fromCode(String code) {
        if (code == null || code.isBlank()) {
            return Optional.empty();
        }
        String normalized = code.trim().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(type -> type.name().equals(normalized))
                .findFirst();
    }
}
