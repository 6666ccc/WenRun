package com.wenrun.service.impl;

import com.wenrun.config.ClinicProperties;
import com.wenrun.repository.ScheduleRepository;
import com.wenrun.vo.ScheduleVO;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ScheduleServiceImplTest {

    private final ScheduleRepository scheduleMapper = mock(ScheduleRepository.class);
    private final ClinicProperties clinic = new ClinicProperties();
    private final ScheduleServiceImpl service = new ScheduleServiceImpl(scheduleMapper, clinic);

    @Test
    void listWithoutWorkDateQueriesFromTodayOnward() {
        ClinicProperties morningClinic = clinicAt(LocalDateTime.of(2026, 9, 3, 10, 0));
        ScheduleServiceImpl morningService = new ScheduleServiceImpl(scheduleMapper, morningClinic);
        LocalDate today = morningClinic.today();
        ScheduleVO schedule = new ScheduleVO();
        schedule.setWorkDate(today);
        schedule.setTimePeriod("下午");
        when(scheduleMapper.selectList(null, null, null, today)).thenReturn(List.of(schedule));

        List<ScheduleVO> result = morningService.list(null, null, null);

        assertEquals(1, result.size());
        verify(scheduleMapper).selectList(null, null, null, today);
    }

    @Test
    void listWithWorkDateKeepsExactDateFilter() {
        LocalDate workDate = clinic.today().plusDays(1);
        when(scheduleMapper.selectList(1L, workDate, 8L, null)).thenReturn(List.of());
        service.list(1L, workDate, 8L);
        verify(scheduleMapper).selectList(1L, workDate, 8L, null);
    }

    @Test
    void listHidesMorningAfterConfiguredNoon() {
        ClinicProperties afternoonClinic = clinicAt(LocalDateTime.of(2026, 9, 3, 13, 0));
        ScheduleServiceImpl afternoonService = new ScheduleServiceImpl(scheduleMapper, afternoonClinic);
        ScheduleVO morning = new ScheduleVO();
        morning.setWorkDate(LocalDate.of(2026, 9, 3));
        morning.setTimePeriod("上午");
        ScheduleVO afternoon = new ScheduleVO();
        afternoon.setWorkDate(LocalDate.of(2026, 9, 3));
        afternoon.setTimePeriod("下午");
        LocalDate today = LocalDate.of(2026, 9, 3);
        when(scheduleMapper.selectList(null, null, null, today)).thenReturn(List.of(morning, afternoon));

        List<ScheduleVO> result = afternoonService.list(null, null, null);

        assertEquals(1, result.size());
        assertEquals("下午", result.getFirst().getTimePeriod());
    }

    private static ClinicProperties clinicAt(LocalDateTime beijingTime) {
        ClinicProperties properties = new ClinicProperties();
        ZoneId zone = ZoneId.of("Asia/Shanghai");
        properties.setTimezone("Asia/Shanghai");
        properties.setMorningEnd(LocalTime.of(12, 0));
        properties.setClock(Clock.fixed(beijingTime.atZone(zone).toInstant(), zone));
        return properties;
    }
}
