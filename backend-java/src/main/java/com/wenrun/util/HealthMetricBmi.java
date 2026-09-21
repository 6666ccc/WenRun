package com.wenrun.util;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * BMI = weight(kg) / height(m)^2，不落库。
 */
public final class HealthMetricBmi {

    private static final BigDecimal CM_PER_METER = new BigDecimal("100");
    private static final int HEIGHT_SCALE = 6;
    private static final int BMI_SCALE = 1;

    private HealthMetricBmi() {
    }

    public static BigDecimal calculate(BigDecimal weightKg, BigDecimal heightCm) {
        if (weightKg == null || heightCm == null || heightCm.compareTo(BigDecimal.ZERO) <= 0) {
            return null;
        }
        BigDecimal heightM = heightCm.divide(CM_PER_METER, HEIGHT_SCALE, RoundingMode.HALF_UP);
        BigDecimal heightSquare = heightM.multiply(heightM);
        if (heightSquare.compareTo(BigDecimal.ZERO) == 0) {
            return null;
        }
        return weightKg.divide(heightSquare, BMI_SCALE, RoundingMode.HALF_UP);
    }
}
