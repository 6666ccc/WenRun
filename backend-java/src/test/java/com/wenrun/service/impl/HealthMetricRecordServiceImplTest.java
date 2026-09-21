package com.wenrun.service.impl;

import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.HealthMetricRecordDTO;
import com.wenrun.entity.HealthMetricRecord;
import com.wenrun.entity.Patient;
import com.wenrun.entity.PatientHealthProfile;
import com.wenrun.repository.HealthMetricRecordRepository;
import com.wenrun.repository.PatientHealthProfileRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.HealthMetricTrendVO;
import com.wenrun.vo.HealthMetricTypeVO;
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
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class HealthMetricRecordServiceImplTest {

    private final HealthMetricRecordRepository metricMapper = mock(HealthMetricRecordRepository.class);
    private final PatientHealthProfileRepository profileMapper = mock(PatientHealthProfileRepository.class);
    private final PatientAccessService patientAccess = mock(PatientAccessService.class);
    private final HealthMetricRecordServiceImpl service =
            new HealthMetricRecordServiceImpl(metricMapper, profileMapper, patientAccess);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void listTypesIncludesBmiAsDerivedAndBloodPressureAsDualLine() {
        List<HealthMetricTypeVO> types = service.listTypes();

        HealthMetricTypeVO bmi = types.stream()
                .filter(item -> "BMI".equals(item.getMetricType()))
                .findFirst()
                .orElseThrow();
        HealthMetricTypeVO bp = types.stream()
                .filter(item -> "BLOOD_PRESSURE".equals(item.getMetricType()))
                .findFirst()
                .orElseThrow();
        assertEquals(Boolean.TRUE, bmi.getDerived());
        assertEquals("kg/m²", bmi.getUnit());
        assertEquals(Boolean.TRUE, bp.getDualLine());
        assertEquals("mmHg", bp.getUnit());
    }

    @Test
    void weightTrendUsesMeasuredAtWindowAndLatestValue() {
        allowPatient(3L);
        HealthMetricRecord older = weight(new BigDecimal("106.2"), LocalDateTime.of(2026, 9, 1, 8, 30));
        HealthMetricRecord latest = weight(new BigDecimal("103.5"), LocalDateTime.of(2026, 9, 18, 7, 0));
        when(metricMapper.selectTrend(eq(3L), eq("WEIGHT"), any())).thenReturn(List.of(older, latest));

        HealthMetricTrendVO vo = service.trend(3L, "WEIGHT", 30);

        ArgumentCaptor<LocalDateTime> fromCaptor = ArgumentCaptor.forClass(LocalDateTime.class);
        verify(metricMapper).selectTrend(eq(3L), eq("WEIGHT"), fromCaptor.capture());
        assertEquals(LocalDate.now().minusDays(29).atStartOfDay(), fromCaptor.getValue());
        assertEquals("体重", vo.getMetricName());
        assertEquals("kg", vo.getUnit());
        assertEquals(0, new BigDecimal("103.5").compareTo(vo.getLatestValue()));
        assertEquals(2, vo.getRecords().size());
        assertEquals(LocalDateTime.of(2026, 9, 1, 8, 30), vo.getRecords().get(0).getMeasuredAt());
        assertNull(vo.getRecords().get(0).getSecondaryValue());
    }

    @Test
    void bloodPressureTrendKeepsSystolicAndDiastolic() {
        allowPatient(3L);
        HealthMetricRecord record = new HealthMetricRecord();
        record.setMetricType("BLOOD_PRESSURE");
        record.setPrimaryValue(new BigDecimal("128"));
        record.setSecondaryValue(new BigDecimal("82"));
        record.setMeasuredAt(LocalDateTime.of(2026, 9, 1, 8, 30));
        when(metricMapper.selectTrend(eq(3L), eq("BLOOD_PRESSURE"), any())).thenReturn(List.of(record));

        HealthMetricTrendVO vo = service.trend(3L, "BLOOD_PRESSURE", 7);

        assertEquals("血压", vo.getMetricName());
        assertEquals(0, new BigDecimal("128").compareTo(vo.getLatestValue()));
        assertEquals(0, new BigDecimal("82").compareTo(vo.getLatestSecondaryValue()));
        assertEquals(0, new BigDecimal("82").compareTo(vo.getRecords().get(0).getSecondaryValue()));
    }

    @Test
    void bmiTrendIsComputedFromCurrentHeightAndWeightHistory() {
        allowPatient(3L);
        PatientHealthProfile profile = new PatientHealthProfile();
        profile.setHeightCm(new BigDecimal("170.0"));
        when(profileMapper.selectByPatientId(3L)).thenReturn(profile);
        HealthMetricRecord weight = weight(new BigDecimal("103.5"), LocalDateTime.of(2026, 9, 10, 8, 0));
        when(metricMapper.selectTrend(eq(3L), eq("WEIGHT"), any())).thenReturn(List.of(weight));

        HealthMetricTrendVO vo = service.trend(3L, "BMI", 90);

        verify(metricMapper).selectTrend(eq(3L), eq("WEIGHT"), any());
        assertEquals("BMI", vo.getMetricType());
        assertEquals("kg/m²", vo.getUnit());
        assertEquals(0, new BigDecimal("35.8").compareTo(vo.getLatestValue()));
        assertEquals(0, new BigDecimal("35.8").compareTo(vo.getRecords().get(0).getPrimaryValue()));
        assertNull(vo.getRecords().get(0).getSecondaryValue());
    }

    @Test
    void bmiTrendRequiresHeightInPatientArchive() {
        allowPatient(3L);
        when(profileMapper.selectByPatientId(3L)).thenReturn(null);

        BusinessException ex = assertThrows(BusinessException.class, () -> service.trend(3L, "BMI", 30));
        assertTrue(ex.getMessage().contains("身高"));
        verify(metricMapper, never()).selectTrend(any(), any(), any());
    }

    @Test
    void rejectsUnsupportedRangeAndMetricType() {
        allowPatient(3L);

        assertThrows(BusinessException.class, () -> service.trend(3L, "WEIGHT", 15));
        assertThrows(BusinessException.class, () -> service.trend(3L, "HEIGHT", 30));
        verify(metricMapper, never()).selectTrend(any(), any(), any());
    }

    @Test
    void createPersistsPatientAndCurrentOperator() {
        login(11L);
        allowPatient(3L);
        when(metricMapper.selectByIdAndPatientId(eq(9L), eq(3L))).thenReturn(savedWeight(9L));
        when(metricMapper.insert(any())).thenAnswer(invocation -> {
            HealthMetricRecord record = invocation.getArgument(0);
            record.setId(9L);
            return 1;
        });

        service.create(3L, weightDto());

        ArgumentCaptor<HealthMetricRecord> captor = ArgumentCaptor.forClass(HealthMetricRecord.class);
        verify(metricMapper).insert(captor.capture());
        assertEquals(3L, captor.getValue().getPatientId());
        assertEquals(11L, captor.getValue().getCreatedByUserId());
        assertEquals("WEIGHT", captor.getValue().getMetricType());
        assertEquals("MANUAL", captor.getValue().getSourceType());
        assertNull(captor.getValue().getSecondaryValue());
    }

    @Test
    void createRejectsBmiAndBloodPressureWithoutDiastolic() {
        allowPatient(3L);
        HealthMetricRecordDTO bmi = weightDto();
        bmi.setMetricType("BMI");
        assertThrows(BusinessException.class, () -> service.create(3L, bmi));

        HealthMetricRecordDTO bp = weightDto();
        bp.setMetricType("BLOOD_PRESSURE");
        bp.setPrimaryValue(new BigDecimal("128"));
        bp.setSecondaryValue(null);
        assertThrows(BusinessException.class, () -> service.create(3L, bp));
        verify(metricMapper, never()).insert(any());
    }

    @Test
    void glucoseKeepsMeasureContextAndRejectsUnknownContext() {
        allowPatient(3L);
        when(metricMapper.insert(any())).thenAnswer(invocation -> {
            HealthMetricRecord record = invocation.getArgument(0);
            record.setId(4L);
            return 1;
        });
        when(metricMapper.selectByIdAndPatientId(4L, 3L)).thenReturn(savedGlucose());

        HealthMetricRecordDTO dto = weightDto();
        dto.setMetricType("BLOOD_GLUCOSE");
        dto.setPrimaryValue(new BigDecimal("5.4"));
        dto.setMeasureContext("FASTING");
        service.create(3L, dto);

        ArgumentCaptor<HealthMetricRecord> captor = ArgumentCaptor.forClass(HealthMetricRecord.class);
        verify(metricMapper).insert(captor.capture());
        assertEquals("FASTING", captor.getValue().getMeasureContext());

        dto.setMeasureContext("after-dinner");
        assertThrows(BusinessException.class, () -> service.create(3L, dto));
    }

    @Test
    void deleteIsLogicalAndPatientScoped() {
        allowPatient(3L);
        when(metricMapper.selectByIdAndPatientId(8L, 3L)).thenReturn(savedWeight(8L));
        when(metricMapper.softDeleteByIdAndPatientId(8L, 3L)).thenReturn(1);

        service.delete(3L, 8L);

        verify(metricMapper).softDeleteByIdAndPatientId(8L, 3L);
    }

    @Test
    void getRejectsRecordOwnedByAnotherPatient() {
        allowPatient(3L);
        when(metricMapper.selectByIdAndPatientId(8L, 3L)).thenReturn(null);

        assertThrows(BusinessException.class, () -> service.get(3L, 8L));
    }

    private void allowPatient(Long patientId) {
        Patient patient = new Patient();
        patient.setId(patientId);
        when(patientAccess.requireAccessible(patientId)).thenReturn(patient);
    }

    private void login(Long userId) {
        UserContext.setUserId(userId);
        UserContext.setAccountType("patient");
    }

    private static HealthMetricRecordDTO weightDto() {
        HealthMetricRecordDTO dto = new HealthMetricRecordDTO();
        dto.setMetricType("WEIGHT");
        dto.setPrimaryValue(new BigDecimal("103.5"));
        dto.setMeasuredAt(LocalDateTime.of(2026, 9, 18, 7, 0));
        return dto;
    }

    private static HealthMetricRecord weight(BigDecimal value, LocalDateTime measuredAt) {
        HealthMetricRecord record = new HealthMetricRecord();
        record.setMetricType("WEIGHT");
        record.setPrimaryValue(value);
        record.setMeasuredAt(measuredAt);
        return record;
    }

    private static HealthMetricRecord savedWeight(Long id) {
        HealthMetricRecord record = weight(new BigDecimal("103.5"), LocalDateTime.of(2026, 9, 18, 7, 0));
        record.setId(id);
        record.setPatientId(3L);
        record.setCreatedByUserId(11L);
        record.setSourceType("MANUAL");
        return record;
    }

    private static HealthMetricRecord savedGlucose() {
        HealthMetricRecord record = new HealthMetricRecord();
        record.setId(4L);
        record.setPatientId(3L);
        record.setCreatedByUserId(11L);
        record.setMetricType("BLOOD_GLUCOSE");
        record.setPrimaryValue(new BigDecimal("5.4"));
        record.setMeasureContext("FASTING");
        record.setSourceType("MANUAL");
        record.setMeasuredAt(LocalDateTime.of(2026, 9, 18, 7, 0));
        return record;
    }
}
