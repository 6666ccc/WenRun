package com.wenrun.util;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class HealthMetricBmiTest {

    @Test
    void calculatesBmiFromKilogramAndCentimeter() {
        BigDecimal bmi = HealthMetricBmi.calculate(new BigDecimal("103.5"), new BigDecimal("170.0"));
        assertEquals(0, new BigDecimal("35.8").compareTo(bmi));
    }

    @Test
    void returnsNullWhenHeightMissing() {
        assertNull(HealthMetricBmi.calculate(new BigDecimal("70"), null));
        assertNull(HealthMetricBmi.calculate(new BigDecimal("70"), BigDecimal.ZERO));
    }
}
