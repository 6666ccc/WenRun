package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.HealthProfileDTO;
import com.wenrun.entity.HealthMetricRecord;
import com.wenrun.entity.Patient;
import com.wenrun.entity.PatientHealthProfile;
import com.wenrun.entity.PatientHealthSnapshot;
import com.wenrun.repository.HealthMetricRecordRepository;
import com.wenrun.repository.PatientHealthProfileRepository;
import com.wenrun.repository.PatientHealthSnapshotRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.HealthProfileVO;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PatientHealthProfileServiceImplTest {

    private final PatientHealthProfileRepository profileMapper = mock(PatientHealthProfileRepository.class);
    private final PatientHealthSnapshotRepository snapshotMapper = mock(PatientHealthSnapshotRepository.class);
    private final HealthMetricRecordRepository metricMapper = mock(HealthMetricRecordRepository.class);
    private final PatientAccessService patientAccess = mock(PatientAccessService.class);
    private final PatientHealthProfileServiceImpl service =
            new PatientHealthProfileServiceImpl(profileMapper, snapshotMapper, metricMapper, patientAccess);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void patientCannotReadAnotherPatientsHealthProfile() {
        loginPatient(11L);
        org.mockito.Mockito.doThrow(new BusinessException("无权访问该患者"))
                .when(patientAccess).assertAccess(2L);

        assertThrows(BusinessException.class, () -> service.get(2L));
    }

    @Test
    void getReturnsEmptyProfileWhenNoneExists() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null);

        HealthProfileVO vo = service.get(1L);

        assertEquals(1L, vo.getPatientId());
        assertEquals(Boolean.FALSE, vo.getExists());
        assertNull(vo.getHeightCm());
    }

    @Test
    void createWritesCurrentProfileAndSnapshot() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null, savedProfile());

        HealthProfileVO vo = service.create(1L, validDto());

        ArgumentCaptor<PatientHealthProfile> profileCaptor = ArgumentCaptor.forClass(PatientHealthProfile.class);
        ArgumentCaptor<PatientHealthSnapshot> snapshotCaptor = ArgumentCaptor.forClass(PatientHealthSnapshot.class);
        verify(profileMapper).insert(profileCaptor.capture());
        verify(snapshotMapper).insert(snapshotCaptor.capture());
        assertEquals(0, new BigDecimal("170.0").compareTo(profileCaptor.getValue().getHeightCm()));
        assertEquals("fasting", snapshotCaptor.getValue().getGlucoseType());
        assertNotNull(snapshotCaptor.getValue().getMeasuredAt());
        assertEquals(Boolean.TRUE, vo.getExists());
        assertEquals(1L, vo.getId());
    }

    @Test
    void createFailsWhenProfileAlreadyExists() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(savedProfile());

        assertThrows(BusinessException.class, () -> service.create(1L, validDto()));
        verify(profileMapper, never()).insert(any());
    }

    @Test
    void updateRewritesCurrentValuesAndAppendsSnapshot() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(savedProfile(), savedProfile());

        service.update(1L, validDto());

        verify(profileMapper).updateById(any(PatientHealthProfile.class));
        verify(snapshotMapper).insert(any(PatientHealthSnapshot.class));
    }

    @Test
    void updateFailsWhenProfileMissing() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null);

        assertThrows(BusinessException.class, () -> service.update(1L, validDto()));
        verify(profileMapper, never()).updateById(any());
    }

    @Test
    void deleteRemovesCurrentProfileOnly() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(savedProfile());

        service.delete(1L);

        verify(profileMapper).deleteByPatientId(1L);
        verify(snapshotMapper, never()).deleteById(any());
    }

    @Test
    void deleteSnapshotRejectsForeignRecord() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        PatientHealthSnapshot snapshot = new PatientHealthSnapshot();
        snapshot.setId(9L);
        snapshot.setPatientId(2L);
        when(snapshotMapper.selectById(9L)).thenReturn(snapshot);

        assertThrows(BusinessException.class, () -> service.deleteSnapshot(1L, 9L));
        verify(snapshotMapper, never()).deleteById(9L);
    }

    @Test
    void rejectsOutOfRangeVitals() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null);
        HealthProfileDTO dto = validDto();
        dto.setSystolicMmhg(400);

        assertThrows(BusinessException.class, () -> service.create(1L, dto));
        verify(profileMapper, never()).insert(any());
    }

    @Test
    void rejectsEmptyPayload() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null);

        assertThrows(BusinessException.class, () -> service.create(1L, new HealthProfileDTO()));
        verify(profileMapper, never()).insert(any());
        verify(metricMapper, never()).insert(any());
    }

    @Test
    void createWritesVitalsOntoMetricTimelineButNotHeightOrDerivedWhtr() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null, savedProfile());

        service.create(1L, validDto());

        ArgumentCaptor<HealthMetricRecord> captor = ArgumentCaptor.forClass(HealthMetricRecord.class);
        verify(metricMapper, times(5)).insert(captor.capture());
        List<String> types = captor.getAllValues().stream().map(HealthMetricRecord::getMetricType).toList();
        assertEquals(List.of("WEIGHT", "WAIST", "BLOOD_PRESSURE", "BLOOD_GLUCOSE", "HEART_RATE"), types);

        HealthMetricRecord weight = captor.getAllValues().get(0);
        assertEquals(1L, weight.getPatientId());
        assertEquals(11L, weight.getCreatedByUserId());
        assertEquals(0, new BigDecimal("62.5").compareTo(weight.getPrimaryValue()));
        assertEquals("MANUAL", weight.getSourceType());
        assertEquals(LocalDateTime.of(2026, 9, 19, 8, 30), weight.getMeasuredAt());

        HealthMetricRecord waist = captor.getAllValues().get(1);
        assertEquals(0, new BigDecimal("85.0").compareTo(waist.getPrimaryValue()));

        HealthMetricRecord pressure = captor.getAllValues().get(2);
        assertEquals(0, new BigDecimal("118").compareTo(pressure.getPrimaryValue()));
        assertEquals(0, new BigDecimal("76").compareTo(pressure.getSecondaryValue()));

        HealthMetricRecord glucose = captor.getAllValues().get(3);
        assertEquals("FASTING", glucose.getMeasureContext());
        assertEquals(0, new BigDecimal("5.4").compareTo(glucose.getPrimaryValue()));
    }

    @Test
    void updateWritesOnlyTheVitalThatChanged() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(completeProfile(), completeProfile());
        HealthProfileDTO dto = validDto();
        dto.setWeightKg(new BigDecimal("63.0"));

        service.update(1L, dto);

        ArgumentCaptor<HealthMetricRecord> captor = ArgumentCaptor.forClass(HealthMetricRecord.class);
        verify(metricMapper, times(1)).insert(captor.capture());
        assertEquals("WEIGHT", captor.getValue().getMetricType());
        assertEquals(0, new BigDecimal("63.0").compareTo(captor.getValue().getPrimaryValue()));
    }

    @Test
    void updateDoesNotWriteMetricsWhenOnlyHistoryChanges() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(completeProfile(), completeProfile());
        HealthProfileDTO dto = validDto();
        dto.setPastHistory("病史有更新");

        service.update(1L, dto);

        verify(metricMapper, never()).insert(any());
    }

    @Test
    void updateWritesSpo2RespiratoryAndTemperatureMetrics() {
        ownPatient(1L, 11L);
        loginPatient(11L);
        when(profileMapper.selectByPatientId(1L)).thenReturn(completeProfile(), completeProfile());
        HealthProfileDTO dto = validDto();
        dto.setSpo2Pct(98);
        dto.setRespiratoryRateBpm(16);
        dto.setTemperatureC(new BigDecimal("36.5"));

        service.update(1L, dto);

        ArgumentCaptor<HealthMetricRecord> captor = ArgumentCaptor.forClass(HealthMetricRecord.class);
        verify(metricMapper, times(3)).insert(captor.capture());
        assertEquals(List.of("SPO2", "RESPIRATORY_RATE", "TEMPERATURE"),
                captor.getAllValues().stream().map(HealthMetricRecord::getMetricType).toList());
        assertEquals(0, new BigDecimal("98").compareTo(captor.getAllValues().get(0).getPrimaryValue()));
        assertEquals(0, new BigDecimal("16").compareTo(captor.getAllValues().get(1).getPrimaryValue()));
        assertEquals(0, new BigDecimal("36.5").compareTo(captor.getAllValues().get(2).getPrimaryValue()));
    }

    @Test
    void writesMetricsByPatientIdEvenWithoutPrimaryAccount() {
        allowPatient(1L);
        UserContext.setUserId(7L);
        UserContext.setAccountType(AccountType.INTERNAL);
        when(profileMapper.selectByPatientId(1L)).thenReturn(null, savedProfile());

        service.create(1L, validDto());

        ArgumentCaptor<HealthMetricRecord> captor = ArgumentCaptor.forClass(HealthMetricRecord.class);
        verify(metricMapper, times(5)).insert(captor.capture());
        assertEquals(1L, captor.getAllValues().get(0).getPatientId());
        assertEquals(7L, captor.getAllValues().get(0).getCreatedByUserId());
        verify(snapshotMapper).insert(any(PatientHealthSnapshot.class));
    }

    private void loginPatient(Long userId) {
        UserContext.setUserId(userId);
        UserContext.setAccountType(AccountType.PATIENT);
    }

    private void allowPatient(Long patientId) {
        Patient patient = new Patient();
        patient.setId(patientId);
        when(patientAccess.requireAccessible(patientId)).thenReturn(patient);
        org.mockito.Mockito.doNothing().when(patientAccess).assertAccess(patientId);
    }

    private void ownPatient(Long patientId, Long userId) {
        allowPatient(patientId);
    }

    private static HealthProfileDTO validDto() {
        HealthProfileDTO dto = new HealthProfileDTO();
        dto.setHeightCm(new BigDecimal("170.0"));
        dto.setWeightKg(new BigDecimal("62.5"));
        dto.setWaistCm(new BigDecimal("85.0"));
        dto.setSystolicMmhg(118);
        dto.setDiastolicMmhg(76);
        dto.setGlucoseMmol(new BigDecimal("5.4"));
        dto.setGlucoseType("fasting");
        dto.setHeartRateBpm(72);
        dto.setMeasuredAt(LocalDateTime.of(2026, 9, 19, 8, 30));
        dto.setPastHistory("无手术史");
        return dto;
    }

    private static PatientHealthProfile savedProfile() {
        PatientHealthProfile profile = new PatientHealthProfile();
        profile.setId(1L);
        profile.setPatientId(1L);
        profile.setHeightCm(new BigDecimal("170.0"));
        profile.setGlucoseType("fasting");
        profile.setMeasuredAt(LocalDateTime.of(2026, 9, 19, 8, 30));
        return profile;
    }

    private static PatientHealthProfile completeProfile() {
        PatientHealthProfile profile = savedProfile();
        profile.setWeightKg(new BigDecimal("62.5"));
        profile.setWaistCm(new BigDecimal("85.0"));
        profile.setSystolicMmhg(118);
        profile.setDiastolicMmhg(76);
        profile.setGlucoseMmol(new BigDecimal("5.4"));
        profile.setHeartRateBpm(72);
        return profile;
    }
}
