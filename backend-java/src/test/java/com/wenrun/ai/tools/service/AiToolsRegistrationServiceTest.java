package com.wenrun.ai.tools.service;

import com.wenrun.ai.delegation.AiDelegationClaims;
import com.wenrun.ai.tools.dto.AiToolRegistrationCreateDTO;
import com.wenrun.ai.tools.exception.AiToolException;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.entity.Patient;
import com.wenrun.entity.Registration;
import com.wenrun.entity.Schedule;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.RegistrationRepository;
import com.wenrun.repository.ScheduleRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiToolsRegistrationServiceTest {

    private RegistrationRepository registrationRepository;
    private ScheduleRepository scheduleRepository;
    private PatientRepository patientRepository;
    private AiToolsRegistrationService service;

    @BeforeEach
    void setUp() {
        registrationRepository = mock(RegistrationRepository.class);
        scheduleRepository = mock(ScheduleRepository.class);
        patientRepository = mock(PatientRepository.class);
        service = new AiToolsRegistrationService(
                registrationRepository, scheduleRepository, patientRepository);
    }

    @Test
    void ignoresBodyPatientAndUsesDelegatedPatient() {
        var dto = new AiToolRegistrationCreateDTO(999L, 20L, "idem-1", "i-1");
        AiToolException error = assertThrows(AiToolException.class,
                () -> service.register(dto, claimsForPatient(10L)));
        assertEquals("INVALID_PATIENT", error.getCode());
    }

    @Test
    void sameIdempotencyKeyReturnsSameRegistration() {
        when(patientRepository.selectById(10L)).thenReturn(patient(10L));
        when(registrationRepository.selectByIdempotencyKey("idem-1")).thenReturn(null, existing(88L));
        when(registrationRepository.countActiveByPatientAndSchedule(10L, 20L, BizStatus.REG_REGISTERED))
                .thenReturn(0);
        when(scheduleRepository.selectByIdForUpdate(20L)).thenReturn(availableSchedule(20L));
        when(scheduleRepository.decrementRemaining(20L)).thenReturn(1);
        when(registrationRepository.insert(any(Registration.class))).thenAnswer(invocation -> {
            Registration registration = invocation.getArgument(0);
            registration.setId(88L);
            return 1;
        });

        Long first = service.register(validRequest("idem-1"), writeClaims());
        Long second = service.register(validRequest("idem-1"), writeClaims());
        assertEquals(first, second);
        verify(scheduleRepository, times(1)).decrementRemaining(anyLong());
    }

    @Test
    void rejectsMissingWriteScope() {
        AiToolException error = assertThrows(AiToolException.class,
                () -> service.register(validRequest("idem-1"), readClaims()));
        assertEquals("INSUFFICIENT_SCOPE", error.getCode());
    }

    @Test
    void rejectsInterruptMismatch() {
        var dto = new AiToolRegistrationCreateDTO(10L, 20L, "idem-1", "other");
        AiToolException error = assertThrows(AiToolException.class,
                () -> service.register(dto, writeClaims()));
        assertEquals("INTERRUPT_MISMATCH", error.getCode());
    }

    private static AiToolRegistrationCreateDTO validRequest(String idempotencyKey) {
        return new AiToolRegistrationCreateDTO(10L, 20L, idempotencyKey, "i-1");
    }

    private static AiDelegationClaims claimsForPatient(Long patientId) {
        return new AiDelegationClaims(1L, patientId, "c-1",
                List.of("registration:create"), "i-1", "jti-1");
    }

    private static AiDelegationClaims writeClaims() {
        return claimsForPatient(10L);
    }

    private static AiDelegationClaims readClaims() {
        return new AiDelegationClaims(1L, 10L, "c-1",
                List.of("dept:read", "doctor:read", "schedule:read"), null, "jti-2");
    }

    private static Patient patient(Long id) {
        Patient patient = new Patient();
        patient.setId(id);
        return patient;
    }

    private static Schedule availableSchedule(Long id) {
        Schedule schedule = new Schedule();
        schedule.setId(id);
        schedule.setDeptId(3L);
        schedule.setStaffId(4L);
        schedule.setRemainingCount(2);
        schedule.setRegisterFee(new BigDecimal("15.00"));
        return schedule;
    }

    private static Registration existing(Long id) {
        Registration registration = new Registration();
        registration.setId(id);
        registration.setIdempotencyKey("idem-1");
        return registration;
    }
}
