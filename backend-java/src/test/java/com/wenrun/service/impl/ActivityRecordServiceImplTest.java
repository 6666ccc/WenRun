package com.wenrun.service.impl;

import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.ExerciseRecordDTO;
import com.wenrun.dto.SleepRecordDTO;
import com.wenrun.entity.Patient;
import com.wenrun.entity.PatientExerciseRecord;
import com.wenrun.entity.PatientSleepRecord;
import com.wenrun.repository.PatientExerciseRecordRepository;
import com.wenrun.repository.PatientSleepRecordRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.ActivitySummaryVO;
import com.wenrun.vo.ExerciseRecordVO;
import com.wenrun.vo.SleepRecordVO;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ActivityRecordServiceImplTest {

    private final PatientExerciseRecordRepository exerciseMapper = mock(PatientExerciseRecordRepository.class);
    private final PatientSleepRecordRepository sleepMapper = mock(PatientSleepRecordRepository.class);
    private final PatientAccessService patientAccess = mock(PatientAccessService.class);
    private final ActivityRecordServiceImpl service =
            new ActivityRecordServiceImpl(exerciseMapper, sleepMapper, patientAccess);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void summaryUsesSevenDayWindowAndKeepsLatestOutsideTheWindow() {
        allowPatient(3L);
        PatientExerciseRecord recent = exercise(9L, 40, 180, LocalDateTime.now().minusDays(1));
        when(exerciseMapper.selectSince(eq(3L), any())).thenReturn(List.of(recent));
        when(exerciseMapper.selectRecent(3L, 1)).thenReturn(List.of(exercise(2L, 20, null, LocalDateTime.now().minusDays(20))));
        PatientSleepRecord sleep = sleep(4L, 480, 4, LocalDateTime.now().minusHours(8));
        when(sleepMapper.selectSince(eq(3L), any())).thenReturn(List.of(sleep));
        when(sleepMapper.selectRecent(3L, 1)).thenReturn(List.of(sleep));

        ActivitySummaryVO vo = service.summary(3L, null);

        ArgumentCaptor<LocalDateTime> fromCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        verify(exerciseMapper).selectSince(eq(3L), fromCaptor.capture());
        assertEquals(LocalDate.now().minusDays(6).atStartOfDay(), fromCaptor.getValue());
        assertEquals(7, vo.getRangeDays());
        assertEquals(1, vo.getExerciseCount());
        assertEquals(40, vo.getExerciseMinutes());
        assertEquals(180, vo.getExerciseCalories());
        assertEquals(1, vo.getSleepCount());
        assertEquals(480, vo.getSleepAvgMinutes());
        assertEquals(2L, vo.getLatestExercise().getId());
        assertEquals("较好", vo.getLatestSleep().getQualityName());
    }

    @Test
    void createExerciseStoresManualSourceAndRecorder() {
        allowPatient(3L);
        UserContext.setUserId(11L);
        when(exerciseMapper.insert(any())).thenAnswer(invocation -> {
            invocation.<PatientExerciseRecord>getArgument(0).setId(8L);
            return 1;
        });
        when(exerciseMapper.selectByIdAndPatientId(8L, 3L)).thenReturn(savedExercise(8L));

        ExerciseRecordVO vo = service.createExercise(3L, exerciseDto());

        ArgumentCaptor<PatientExerciseRecord> captor = ArgumentCaptor.forClass(PatientExerciseRecord.class);
        verify(exerciseMapper).insert(captor.capture());
        PatientExerciseRecord saved = captor.getValue();
        assertEquals(3L, saved.getPatientId());
        assertEquals(11L, saved.getCreatedByUserId());
        assertEquals("RUN", saved.getExerciseType());
        assertEquals("MANUAL", saved.getSourceType());
        assertEquals(0, new BigDecimal("5.20").compareTo(saved.getDistanceKm()));
        assertEquals("跑步", vo.getExerciseName());
        assertEquals("中等", vo.getIntensityName());
    }

    @Test
    void createExerciseRejectsFutureStartAndUnknownType() {
        allowPatient(3L);
        ExerciseRecordDTO future = exerciseDto();
        future.setStartedAt(LocalDateTime.now().plusHours(2));
        assertEquals("运动开始时间不能晚于当前时间",
                assertThrows(BusinessException.class, () -> service.createExercise(3L, future)).getMessage());

        ExerciseRecordDTO unknown = exerciseDto();
        unknown.setExerciseType("FLY");
        assertEquals("请选择运动类型",
                assertThrows(BusinessException.class, () -> service.createExercise(3L, unknown)).getMessage());
    }

    @Test
    void createSleepComputesDurationFromBedAndWake() {
        allowPatient(3L);
        UserContext.setUserId(11L);
        when(sleepMapper.insert(any())).thenAnswer(invocation -> {
            invocation.<PatientSleepRecord>getArgument(0).setId(6L);
            return 1;
        });
        when(sleepMapper.selectByIdAndPatientId(6L, 3L)).thenReturn(savedSleep(6L));

        SleepRecordDTO dto = new SleepRecordDTO();
        dto.setBedtime(LocalDateTime.of(2026, 9, 23, 23, 10));
        dto.setWakeTime(LocalDateTime.of(2026, 9, 24, 7, 0));
        dto.setQuality(5);
        dto.setRemark("  睡得安稳  ");

        SleepRecordVO vo = service.createSleep(3L, dto);

        ArgumentCaptor<PatientSleepRecord> captor = ArgumentCaptor.forClass(PatientSleepRecord.class);
        verify(sleepMapper).insert(captor.capture());
        assertEquals(470, captor.getValue().getDurationMin());
        assertEquals(5, captor.getValue().getQuality());
        assertEquals("睡得安稳", captor.getValue().getRemark());
        assertEquals("很好", vo.getQualityName());
    }

    @Test
    void createSleepRejectsWakeBeforeBedAndOutOfRangeDuration() {
        allowPatient(3L);
        SleepRecordDTO inverted = sleepDto();
        inverted.setWakeTime(inverted.getBedtime().minusHours(1));
        assertEquals("醒来时间应晚于入睡时间",
                assertThrows(BusinessException.class, () -> service.createSleep(3L, inverted)).getMessage());

        SleepRecordDTO nap = sleepDto();
        nap.setWakeTime(nap.getBedtime().plusMinutes(5));
        assertEquals("睡眠时长应在 10 分钟到 20 小时之间",
                assertThrows(BusinessException.class, () -> service.createSleep(3L, nap)).getMessage());
    }

    @Test
    void deleteExerciseIsLogicalAndPatientScoped() {
        allowPatient(3L);
        when(exerciseMapper.selectByIdAndPatientId(8L, 3L)).thenReturn(savedExercise(8L));
        when(exerciseMapper.softDeleteByIdAndPatientId(8L, 3L)).thenReturn(1);

        service.deleteExercise(3L, 8L);

        verify(exerciseMapper).softDeleteByIdAndPatientId(8L, 3L);
    }

    @Test
    void getSleepRejectsRecordOwnedByAnotherPatient() {
        allowPatient(3L);
        when(sleepMapper.selectByIdAndPatientId(6L, 3L)).thenReturn(null);

        assertThrows(BusinessException.class, () -> service.getSleep(3L, 6L));
    }

    @Test
    void caloriesStayEmptyWhenNoRecordHasCalories() {
        allowPatient(3L);
        when(exerciseMapper.selectSince(eq(3L), any())).thenReturn(List.of(exercise(1L, 30, null, LocalDateTime.now().minusHours(2))));
        when(exerciseMapper.selectRecent(3L, 1)).thenReturn(List.of());
        when(sleepMapper.selectSince(eq(3L), any())).thenReturn(List.of());
        when(sleepMapper.selectRecent(3L, 1)).thenReturn(List.of());

        ActivitySummaryVO vo = service.summary(3L, 30);

        assertNull(vo.getExerciseCalories());
        assertNull(vo.getSleepAvgMinutes());
        assertEquals(30, vo.getRangeDays());
    }

    private void allowPatient(Long patientId) {
        Patient patient = new Patient();
        patient.setId(patientId);
        when(patientAccess.requireAccessible(patientId)).thenReturn(patient);
    }

    private static ExerciseRecordDTO exerciseDto() {
        ExerciseRecordDTO dto = new ExerciseRecordDTO();
        dto.setExerciseType("run");
        dto.setDurationMin(35);
        dto.setDistanceKm(new BigDecimal("5.2"));
        dto.setCaloriesKcal(320);
        dto.setIntensity("moderate");
        dto.setStartedAt(LocalDateTime.of(2026, 9, 24, 7, 30));
        return dto;
    }

    private static SleepRecordDTO sleepDto() {
        SleepRecordDTO dto = new SleepRecordDTO();
        dto.setBedtime(LocalDateTime.of(2026, 9, 23, 23, 0));
        dto.setWakeTime(LocalDateTime.of(2026, 9, 24, 6, 30));
        dto.setQuality(3);
        return dto;
    }

    private static PatientExerciseRecord exercise(Long id, int minutes, Integer calories, LocalDateTime startedAt) {
        PatientExerciseRecord record = new PatientExerciseRecord();
        record.setId(id);
        record.setPatientId(3L);
        record.setExerciseType("WALK");
        record.setDurationMin(minutes);
        record.setCaloriesKcal(calories);
        record.setStartedAt(startedAt);
        record.setSourceType("MANUAL");
        return record;
    }

    private static PatientExerciseRecord savedExercise(Long id) {
        PatientExerciseRecord record = exercise(id, 35, 320, LocalDateTime.of(2026, 9, 24, 7, 30));
        record.setExerciseType("RUN");
        record.setIntensity("MODERATE");
        record.setDistanceKm(new BigDecimal("5.20"));
        record.setCreatedByUserId(11L);
        return record;
    }

    private static PatientSleepRecord sleep(Long id, int minutes, int quality, LocalDateTime wakeTime) {
        PatientSleepRecord record = new PatientSleepRecord();
        record.setId(id);
        record.setPatientId(3L);
        record.setDurationMin(minutes);
        record.setQuality(quality);
        record.setBedtime(wakeTime.minusMinutes(minutes));
        record.setWakeTime(wakeTime);
        record.setSourceType("MANUAL");
        return record;
    }

    private static PatientSleepRecord savedSleep(Long id) {
        return sleep(id, 470, 5, LocalDateTime.of(2026, 9, 24, 7, 0));
    }
}
