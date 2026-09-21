package com.wenrun.enums;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class HealthMetricTypeTest {

    @Test
    void storesEnglishCodeWithFixedChineseNameAndUnit() {
        assertEquals("WEIGHT", HealthMetricType.WEIGHT.getCode());
        assertEquals("体重", HealthMetricType.WEIGHT.getDisplayName());
        assertEquals("kg", HealthMetricType.WEIGHT.getUnit());
        assertEquals("mmHg", HealthMetricType.BLOOD_PRESSURE.getUnit());
        assertEquals("mmol/L", HealthMetricType.BLOOD_GLUCOSE.getUnit());
        assertEquals("次/分", HealthMetricType.HEART_RATE.getUnit());
        assertEquals("%", HealthMetricType.SPO2.getUnit());
        assertEquals("℃", HealthMetricType.TEMPERATURE.getUnit());
        assertEquals("次/分", HealthMetricType.RESPIRATORY_RATE.getUnit());
        assertEquals("cm", HealthMetricType.WAIST.getUnit());
    }

    @Test
    void bmiIsDerivedAndBloodPressureUsesDualLine() {
        assertFalse(HealthMetricType.BMI.isPersisted());
        assertEquals("kg/m²", HealthMetricType.BMI.getUnit());
        assertTrue(HealthMetricType.WEIGHT.isPersisted());
        assertTrue(HealthMetricType.BLOOD_PRESSURE.isDualLine());
        assertFalse(HealthMetricType.WEIGHT.isDualLine());
    }

    @Test
    void fromCodeAcceptsEnglishEnumValueIgnoreCase() {
        assertEquals(HealthMetricType.BLOOD_PRESSURE, HealthMetricType.fromCode("blood_pressure").orElseThrow());
        assertTrue(HealthMetricType.fromCode("身高").isEmpty());
        assertTrue(HealthMetricType.fromCode(null).isEmpty());
    }
}
