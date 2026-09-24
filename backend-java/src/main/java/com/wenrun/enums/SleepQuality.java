package com.wenrun.enums;

import java.util.Arrays;
import java.util.Optional;

/**
 * 睡眠质量 1–5。数据库存分值。
 */
public enum SleepQuality {

    VERY_POOR(1, "很差"),
    POOR(2, "较差"),
    FAIR(3, "一般"),
    GOOD(4, "较好"),
    EXCELLENT(5, "很好");

    private final int score;
    private final String displayName;

    SleepQuality(int score, String displayName) {
        this.score = score;
        this.displayName = displayName;
    }

    public int getScore() {
        return score;
    }

    public String getDisplayName() {
        return displayName;
    }

    public static Optional<SleepQuality> fromScore(Integer score) {
        if (score == null) {
            return Optional.empty();
        }
        return Arrays.stream(values())
                .filter(item -> item.score == score)
                .findFirst();
    }
}
