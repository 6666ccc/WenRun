package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.Patient;
import com.wenrun.repository.PatientRepository;
import com.wenrun.service.PatientAccessService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PatientServiceImplTest {

    private final PatientRepository patientMapper = mock(PatientRepository.class);
    private final PatientAccessService patientAccess = mock(PatientAccessService.class);
    private final PatientServiceImpl service = new PatientServiceImpl(patientMapper, patientAccess);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void patientCannotReadAnotherPatientsProfile() {
        UserContext.setUserId(11L);
        UserContext.setAccountType(AccountType.PATIENT);
        doThrow(new BusinessException("无权访问该患者")).when(patientAccess).requireAccessible(2L);

        assertThrows(BusinessException.class, () -> service.getById(2L));
    }

    @Test
    void createBindsSelfRelationForPrimaryAccount() {
        Patient patient = new Patient();
        patient.setName("本人");
        patient.setUserId(5L);
        when(patientMapper.insert(patient)).thenAnswer(invocation -> {
            patient.setId(3L);
            return 1;
        });

        service.create(patient);

        org.mockito.Mockito.verify(patientAccess).bindSelf(5L, 3L);
    }
}
