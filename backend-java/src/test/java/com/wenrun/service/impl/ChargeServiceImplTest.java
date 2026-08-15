package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.OutpatientVisit;
import com.wenrun.entity.Patient;
import com.wenrun.entity.Registration;
import com.wenrun.repository.ChargeDetailRepository;
import com.wenrun.repository.ChargeOrderRepository;
import com.wenrun.repository.ExamRequestRepository;
import com.wenrun.repository.MedicalItemRepository;
import com.wenrun.repository.OutpatientVisitRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.PrescriptionRepository;
import com.wenrun.repository.RegistrationRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ChargeServiceImplTest {

    private final ChargeOrderRepository chargeOrderMapper = mock(ChargeOrderRepository.class);
    private final ChargeDetailRepository chargeDetailMapper = mock(ChargeDetailRepository.class);
    private final OutpatientVisitRepository visitMapper = mock(OutpatientVisitRepository.class);
    private final RegistrationRepository registrationMapper = mock(RegistrationRepository.class);
    private final PrescriptionRepository prescriptionMapper = mock(PrescriptionRepository.class);
    private final ExamRequestRepository examRequestMapper = mock(ExamRequestRepository.class);
    private final MedicalItemRepository medicalItemMapper = mock(MedicalItemRepository.class);
    private final PatientRepository patientMapper = mock(PatientRepository.class);
    private final ChargeServiceImpl service = new ChargeServiceImpl(chargeOrderMapper, chargeDetailMapper,
            visitMapper, registrationMapper, prescriptionMapper, examRequestMapper, medicalItemMapper, patientMapper);

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void patientCannotCreateChargeOrderForAnotherPatientsVisit() {
        OutpatientVisit visit = new OutpatientVisit();
        visit.setId(3L);
        visit.setPatientId(2L);
        visit.setRegistrationId(4L);
        Registration registration = new Registration();
        registration.setId(4L);
        registration.setRegFee(BigDecimal.TEN);
        Patient currentPatient = new Patient();
        currentPatient.setId(1L);

        when(visitMapper.selectById(3L)).thenReturn(visit);
        when(patientMapper.selectByUserId(11L)).thenReturn(currentPatient);
        when(registrationMapper.selectById(4L)).thenReturn(registration);
        when(chargeDetailMapper.countByBiz(BizStatus.CHARGE_REG, 4L)).thenReturn(0);
        UserContext.setUserId(11L);
        UserContext.setAccountType(AccountType.PATIENT);

        assertThrows(BusinessException.class, () -> service.createFromVisit(3L));

        verify(chargeOrderMapper, never()).insert(org.mockito.ArgumentMatchers.any());
    }
}
