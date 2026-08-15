package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.Patient;
import com.wenrun.repository.PatientRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PatientServiceImplTest {

    private final PatientRepository patientMapper = mock(PatientRepository.class);
    private final PatientServiceImpl service = new PatientServiceImpl(patientMapper);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void patientCannotReadAnotherPatientsProfile() {
        Patient patient = new Patient();
        patient.setId(2L);
        patient.setUserId(22L);
        when(patientMapper.selectById(2L)).thenReturn(patient);
        UserContext.setUserId(11L);
        UserContext.setAccountType(AccountType.PATIENT);

        assertThrows(BusinessException.class, () -> service.getById(2L));
    }
}
