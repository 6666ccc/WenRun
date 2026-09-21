package com.wenrun.service.impl;

import com.wenrun.common.ResultCode;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.Patient;
import com.wenrun.entity.UserPatientRelation;
import com.wenrun.enums.RelationType;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.UserPatientRelationRepository;
import com.wenrun.vo.AccessiblePatientVO;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PatientAccessServiceImplTest {

    private final UserPatientRelationRepository relationMapper = mock(UserPatientRelationRepository.class);
    private final PatientRepository patientMapper = mock(PatientRepository.class);
    private final PatientAccessServiceImpl service = new PatientAccessServiceImpl(relationMapper, patientMapper);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void patientAccountCanAccessRelatedPatientEvenWhenIdsDiffer() {
        loginPatient(5L);
        when(patientMapper.selectById(3L)).thenReturn(patient(3L, 5L));
        when(relationMapper.selectActive(5L, 3L)).thenReturn(selfRelation(5L, 3L));

        assertTrue(service.hasAccess(3L));
        assertEquals(3L, service.requireAccessible(3L).getId());
    }

    @Test
    void equalNumericIdsAreNotTreatedAsTheSameEntity() {
        loginPatient(5L);
        when(patientMapper.selectById(5L)).thenReturn(patient(5L, 99L));
        when(relationMapper.selectActive(5L, 5L)).thenReturn(null);

        assertFalse(service.hasAccess(5L));
        BusinessException error = assertThrows(BusinessException.class, () -> service.assertAccess(5L));
        assertEquals(ResultCode.FORBIDDEN, error.getCode());
        assertEquals("无权访问该患者", error.getMessage());
    }

    @Test
    void patientAccountCannotAccessUnrelatedPatient() {
        loginPatient(5L);
        when(patientMapper.selectById(99L)).thenReturn(patient(99L, 8L));
        when(relationMapper.selectActive(5L, 99L)).thenReturn(null);

        BusinessException error = assertThrows(BusinessException.class, () -> service.assertAccess(99L));
        assertEquals(ResultCode.FORBIDDEN, error.getCode());
    }

    @Test
    void missingPatientIsNotFoundRatherThanForbidden() {
        loginPatient(5L);
        when(patientMapper.selectById(99L)).thenReturn(null);

        BusinessException error = assertThrows(BusinessException.class, () -> service.assertAccess(99L));
        assertEquals("患者不存在", error.getMessage());
        verify(relationMapper, never()).selectActive(any(), any());
    }

    @Test
    void staffCanAccessAnyExistingPatientWithoutRelation() {
        UserContext.setUserId(7L);
        UserContext.setAccountType(AccountType.STAFF);
        when(patientMapper.selectById(12L)).thenReturn(patient(12L, 5L));

        assertTrue(service.hasAccess(12L));
        verify(relationMapper, never()).selectActive(any(), any());
    }

    @Test
    void resolvePatientIdUsesRequestedSubjectAfterAccessCheck() {
        loginPatient(5L);
        when(patientMapper.selectById(12L)).thenReturn(patient(12L, null));
        when(relationMapper.selectActive(5L, 12L)).thenReturn(childRelation(5L, 12L));

        assertEquals(12L, service.resolvePatientId(12L));
    }

    @Test
    void resolvePatientIdFallsBackToDefaultRelation() {
        loginPatient(5L);
        AccessiblePatientVO self = accessible(3L, "本人", RelationType.SELF.getCode(), true);
        AccessiblePatientVO child = accessible(12L, "孩子", RelationType.CHILD.getCode(), false);
        when(relationMapper.selectAccessibleByUserId(5L)).thenReturn(List.of(self, child));
        when(patientMapper.selectById(3L)).thenReturn(patient(3L, 5L));
        when(relationMapper.selectActive(5L, 3L)).thenReturn(selfRelation(5L, 3L));

        assertEquals(3L, service.resolvePatientId(null));
        assertEquals(3L, service.defaultPatientId(5L));
    }

    @Test
    void bindSelfCreatesDefaultSelfRelation() {
        when(relationMapper.selectByUserIdAndPatientId(5L, 3L)).thenReturn(null);
        when(relationMapper.countActiveByUserId(5L)).thenReturn(0);

        service.bindSelf(5L, 3L);

        ArgumentCaptor<UserPatientRelation> captor = ArgumentCaptor.forClass(UserPatientRelation.class);
        verify(relationMapper).insert(captor.capture());
        UserPatientRelation saved = captor.getValue();
        assertEquals(5L, saved.getUserId());
        assertEquals(3L, saved.getPatientId());
        assertEquals(RelationType.SELF.getCode(), saved.getRelationType());
        assertEquals(1, saved.getIsDefault());
        assertEquals(1, saved.getStatus());
    }

    @Test
    void bindSelfIsIdempotentWhenRelationAlreadyExists() {
        when(relationMapper.selectByUserIdAndPatientId(5L, 3L)).thenReturn(selfRelation(5L, 3L));

        service.bindSelf(5L, 3L);

        verify(relationMapper, never()).insert(any());
    }

    private static void loginPatient(Long userId) {
        UserContext.setUserId(userId);
        UserContext.setAccountType(AccountType.PATIENT);
    }

    private static Patient patient(Long id, Long userId) {
        Patient patient = new Patient();
        patient.setId(id);
        patient.setUserId(userId);
        return patient;
    }

    private static UserPatientRelation selfRelation(Long userId, Long patientId) {
        UserPatientRelation relation = new UserPatientRelation();
        relation.setUserId(userId);
        relation.setPatientId(patientId);
        relation.setRelationType(RelationType.SELF.getCode());
        relation.setIsDefault(1);
        relation.setStatus(1);
        return relation;
    }

    private static UserPatientRelation childRelation(Long userId, Long patientId) {
        UserPatientRelation relation = selfRelation(userId, patientId);
        relation.setRelationType(RelationType.CHILD.getCode());
        relation.setIsDefault(0);
        return relation;
    }

    private static AccessiblePatientVO accessible(Long patientId, String name, String relationType, boolean isDefault) {
        AccessiblePatientVO vo = new AccessiblePatientVO();
        vo.setPatientId(patientId);
        vo.setName(name);
        vo.setRelationType(relationType);
        vo.setIsDefault(isDefault);
        return vo;
    }
}
