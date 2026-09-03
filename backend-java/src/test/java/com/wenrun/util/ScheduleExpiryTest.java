package com.wenrun.util;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.time.LocalTime;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ScheduleExpiryTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 9, 3);
    private static final ScheduleCutoffs CUTOFFS = new ScheduleCutoffs(
            LocalTime.of(12, 0), LocalTime.of(18, 0), LocalTime.of(21, 0));

    @Test
    void pastWorkDateIsExpired() {
        assertTrue(ScheduleExpiry.isExpired(
                LocalDate.of(2026, 9, 1), "下午",
                TODAY, LocalTime.of(15, 21), CUTOFFS));
    }

    @Test
    void todayAndFutureWorkDatesAreBookableInTheMorning() {
        LocalTime morning = LocalTime.of(9, 0);
        assertFalse(ScheduleExpiry.isExpired(TODAY, "下午", TODAY, morning, CUTOFFS));
        assertFalse(ScheduleExpiry.isExpired(TODAY.plusDays(1), "上午", TODAY, morning, CUTOFFS));
    }

    @Test
    void morningSlotIsHiddenFromConfiguredNoonOnward() {
        assertFalse(ScheduleExpiry.isExpired(TODAY, "上午", TODAY, LocalTime.of(11, 59), CUTOFFS));
        assertTrue(ScheduleExpiry.isExpired(TODAY, "上午", TODAY, LocalTime.of(12, 0), CUTOFFS));
        assertTrue(ScheduleExpiry.isExpired(TODAY, "上午", TODAY, LocalTime.of(13, 0), CUTOFFS));
        assertFalse(ScheduleExpiry.isExpired(TODAY, "下午", TODAY, LocalTime.of(13, 0), CUTOFFS));
    }

    @Test
    void morningEndIsConfigurable() {
        ScheduleCutoffs eleven = new ScheduleCutoffs(
                LocalTime.of(11, 0), LocalTime.of(18, 0), LocalTime.of(21, 0));
        assertTrue(ScheduleExpiry.isExpired(TODAY, "上午", TODAY, LocalTime.of(11, 30), eleven));
        assertFalse(ScheduleExpiry.isExpired(TODAY, "上午", TODAY, LocalTime.of(10, 59), eleven));
    }
}
