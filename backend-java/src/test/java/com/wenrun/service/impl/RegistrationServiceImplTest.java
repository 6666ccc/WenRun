package com.wenrun.service.impl;

import com.wenrun.config.ClinicProperties;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.entity.Patient;
import com.wenrun.entity.Schedule;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.RegistrationRepository;
import com.wenrun.repository.ScheduleRepository;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RegistrationServiceImplTest {

    private final RegistrationRepository registrationMapper = mock(RegistrationRepository.class);
    private final ScheduleRepository scheduleMapper = mock(ScheduleRepository.class);
    private final PatientRepository patientMapper = mock(PatientRepository.class);
    private final ClinicProperties clinic = new ClinicProperties();
    private final RegistrationServiceImpl service = new RegistrationServiceImpl(
            registrationMapper, scheduleMapper, patientMapper, clinic);

    @Test
    void registerRejectsPastSchedule() {
        Patient patient = new Patient();
        patient.setId(1L);
        Schedule schedule = new Schedule();
        schedule.setId(9L);
        schedule.setWorkDate(clinic.today().minusDays(2));
        schedule.setTimePeriod("下午");
        schedule.setRemainingCount(19);
        when(patientMapper.selectById(1L)).thenReturn(patient);
        when(scheduleMapper.selectByIdForUpdate(9L)).thenReturn(schedule);

        RegistrationCreateDTO dto = new RegistrationCreateDTO();
        dto.setPatientId(1L);
        dto.setScheduleId(9L);

        BusinessException error = assertThrows(BusinessException.class, () -> service.register(dto));

        assertEquals("该排班已过期，无法挂号", error.getMessage());
        verify(scheduleMapper, never()).decrementRemaining(anyLong());
        verify(registrationMapper, never()).insert(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void registerRejectsDuplicateDoctorDayPeriod() {
        Patient patient = new Patient();
        patient.setId(1L);
        Schedule schedule = new Schedule();
        schedule.setId(9L);
        schedule.setStaffId(8L);
        schedule.setWorkDate(clinic.today().plusDays(1));
        schedule.setTimePeriod("下午");
        schedule.setRemainingCount(19);
        when(patientMapper.selectById(1L)).thenReturn(patient);
        when(scheduleMapper.selectByIdForUpdate(9L)).thenReturn(schedule);
        when(registrationMapper.countActiveByPatientAndSlot(1L, 8L, schedule.getWorkDate(), "下午"))
                .thenReturn(1);

        RegistrationCreateDTO dto = new RegistrationCreateDTO();
        dto.setPatientId(1L);
        dto.setScheduleId(9L);

        BusinessException error = assertThrows(BusinessException.class, () -> service.register(dto));

        assertEquals("您已预约该医生此时段，不能重复挂号", error.getMessage());
        verify(scheduleMapper, never()).decrementRemaining(anyLong());
        verify(registrationMapper, never()).insert(org.mockito.ArgumentMatchers.any());
    }
}
