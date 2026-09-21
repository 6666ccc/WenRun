package com.wenrun.service.impl;

import com.wenrun.config.ClinicProperties;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.entity.Patient;
import com.wenrun.entity.Registration;
import com.wenrun.entity.Schedule;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.RegistrationRepository;
import com.wenrun.repository.ScheduleRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.RegistrationVO;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DuplicateKeyException;

import java.time.LocalDate;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
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
    private final PatientAccessService patientAccess = mock(PatientAccessService.class);
    private final RegistrationServiceImpl service = new RegistrationServiceImpl(
            registrationMapper, scheduleMapper, patientMapper, clinic, patientAccess);

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

    private Schedule bookableSchedule() {
        Schedule schedule = new Schedule();
        schedule.setId(9L);
        schedule.setStaffId(8L);
        schedule.setDeptId(3L);
        schedule.setWorkDate(clinic.today().plusDays(1));
        schedule.setTimePeriod("下午");
        schedule.setRemainingCount(19);
        return schedule;
    }

    private void givenPatientAndSchedule(Schedule schedule) {
        Patient patient = new Patient();
        patient.setId(1L);
        when(patientMapper.selectById(1L)).thenReturn(patient);
        when(scheduleMapper.selectByIdForUpdate(9L)).thenReturn(schedule);
    }

    private RegistrationCreateDTO dtoWithKey(String idempotencyKey) {
        RegistrationCreateDTO dto = new RegistrationCreateDTO();
        dto.setPatientId(1L);
        dto.setScheduleId(9L);
        dto.setIdempotencyKey(idempotencyKey);
        return dto;
    }

    @Test
    void registerReturnsExistingOrderWhenIdempotencyKeyIsReplayed() {
        givenPatientAndSchedule(bookableSchedule());
        Registration existing = new Registration();
        existing.setId(77L);
        existing.setPatientId(1L);
        when(registrationMapper.selectByIdempotencyKey("ai-reg-001")).thenReturn(existing);

        assertEquals(77L, service.register(dtoWithKey("ai-reg-001")));

        verify(scheduleMapper, never()).decrementRemaining(anyLong());
        verify(registrationMapper, never()).insert(any());
    }

    @Test
    void registerReplaysSuccessfullyEvenAfterScheduleExpired() {
        Schedule expired = bookableSchedule();
        expired.setWorkDate(clinic.today().minusDays(2));
        givenPatientAndSchedule(expired);
        Registration existing = new Registration();
        existing.setId(77L);
        existing.setPatientId(1L);
        when(registrationMapper.selectByIdempotencyKey("ai-reg-001")).thenReturn(existing);

        assertEquals(77L, service.register(dtoWithKey("ai-reg-001")));
    }

    @Test
    void registerRejectsIdempotencyKeyOwnedByAnotherPatient() {
        givenPatientAndSchedule(bookableSchedule());
        Registration other = new Registration();
        other.setId(77L);
        other.setPatientId(2L);
        when(registrationMapper.selectByIdempotencyKey("ai-reg-001")).thenReturn(other);

        BusinessException error = assertThrows(
                BusinessException.class, () -> service.register(dtoWithKey("ai-reg-001")));

        assertEquals("幂等键已被占用，请更换后重试", error.getMessage());
        verify(scheduleMapper, never()).decrementRemaining(anyLong());
    }

    @Test
    void registerPersistsIdempotencyKeyOnInsert() {
        givenPatientAndSchedule(bookableSchedule());
        when(scheduleMapper.decrementRemaining(9L)).thenReturn(1);
        ArgumentCaptor<Registration> saved = ArgumentCaptor.forClass(Registration.class);

        service.register(dtoWithKey("ai-reg-001"));

        verify(registrationMapper).insert(saved.capture());
        assertEquals("ai-reg-001", saved.getValue().getIdempotencyKey());
    }

    @Test
    void registerTreatsBlankIdempotencyKeyAsAbsent() {
        givenPatientAndSchedule(bookableSchedule());
        when(scheduleMapper.decrementRemaining(9L)).thenReturn(1);
        ArgumentCaptor<Registration> saved = ArgumentCaptor.forClass(Registration.class);

        service.register(dtoWithKey("   "));

        verify(registrationMapper, never()).selectByIdempotencyKey(org.mockito.ArgumentMatchers.anyString());
        verify(registrationMapper).insert(saved.capture());
        assertNull(saved.getValue().getIdempotencyKey());
    }

    @Test
    void registerTranslatesUniqueIndexViolationIntoBusinessError() {
        givenPatientAndSchedule(bookableSchedule());
        when(scheduleMapper.decrementRemaining(9L)).thenReturn(1);
        when(registrationMapper.insert(any()))
                .thenThrow(new DuplicateKeyException("uk_registration_idempotency_key"));

        BusinessException error = assertThrows(
                BusinessException.class, () -> service.register(dtoWithKey("ai-reg-001")));

        assertEquals("请勿重复提交挂号请求", error.getMessage());
    }

    private RegistrationVO registeredVO(LocalDate workDate) {
        RegistrationVO vo = new RegistrationVO();
        vo.setId(55L);
        vo.setScheduleId(9L);
        vo.setStatus(BizStatus.REG_REGISTERED);
        vo.setWorkDate(workDate);
        vo.setTimePeriod("上午");
        return vo;
    }

    @Test
    void listReleasesSeatWhenExpiredRegistrationIsAutoCancelled() {
        RegistrationVO expired = registeredVO(clinic.today().minusDays(1));
        when(registrationMapper.selectList(1L, null, null, null))
                .thenReturn(List.of(expired));
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(1);

        List<RegistrationVO> result = service.list(1L, null, null, null);

        assertEquals(BizStatus.REG_CANCELLED, result.get(0).getStatus());
        verify(scheduleMapper).incrementRemaining(9L);
    }

    @Test
    void listDoesNotReleaseSeatWhenAnotherRequestAlreadyCancelled() {
        RegistrationVO expired = registeredVO(clinic.today().minusDays(1));
        when(registrationMapper.selectList(1L, null, null, null))
                .thenReturn(List.of(expired));
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(0);

        service.list(1L, null, null, null);

        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }

    @Test
    void listLeavesUnexpiredRegistrationUntouched() {
        RegistrationVO upcoming = registeredVO(clinic.today().plusDays(1));
        when(registrationMapper.selectList(1L, null, null, null))
                .thenReturn(List.of(upcoming));

        List<RegistrationVO> result = service.list(1L, null, null, null);

        assertEquals(BizStatus.REG_REGISTERED, result.get(0).getStatus());
        verify(registrationMapper, never())
                .updateStatusIfCurrent(anyLong(), org.mockito.ArgumentMatchers.anyInt(), org.mockito.ArgumentMatchers.anyInt());
        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }

    @Test
    void cancelReleasesSeatWhenStatusTransitionWins() {
        Registration reg = new Registration();
        reg.setId(55L);
        reg.setPatientId(1L);
        reg.setScheduleId(9L);
        reg.setStatus(BizStatus.REG_REGISTERED);
        when(registrationMapper.selectById(55L)).thenReturn(reg);
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(1);

        service.cancel(55L);

        verify(scheduleMapper).incrementRemaining(9L);
    }

    @Test
    void cancelRejectsWhenStatusChangedConcurrently() {
        Registration reg = new Registration();
        reg.setId(55L);
        reg.setPatientId(1L);
        reg.setScheduleId(9L);
        reg.setStatus(BizStatus.REG_REGISTERED);
        when(registrationMapper.selectById(55L)).thenReturn(reg);
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(0);

        BusinessException error = assertThrows(BusinessException.class, () -> service.cancel(55L));

        assertEquals("挂号单状态已变化，请刷新后重试", error.getMessage());
        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }

    @Test
    void rescheduleMovesSeatWithinOneRegistration() {
        Registration reg = new Registration();
        reg.setId(55L);
        reg.setPatientId(1L);
        reg.setScheduleId(9L);
        reg.setStatus(BizStatus.REG_REGISTERED);
        Schedule current = bookableSchedule();
        Schedule target = bookableSchedule();
        target.setId(12L);
        target.setStaffId(18L);
        target.setRemainingCount(3);
        when(registrationMapper.selectByIdForUpdate(55L)).thenReturn(reg);
        when(scheduleMapper.selectByIdForUpdate(9L)).thenReturn(current);
        when(scheduleMapper.selectByIdForUpdate(12L)).thenReturn(target);
        when(scheduleMapper.decrementRemaining(12L)).thenReturn(1);
        when(registrationMapper.updateScheduleIfCurrent(
                55L, 9L, BizStatus.REG_REGISTERED, 12L,
                target.getDeptId(), target.getStaffId(), target.getRegisterFee())).thenReturn(1);

        service.reschedule(55L, 12L);

        verify(scheduleMapper).decrementRemaining(12L);
        verify(scheduleMapper).incrementRemaining(9L);
    }

    @Test
    void rescheduleRejectsFullTargetWithoutReleasingCurrentSeat() {
        Registration reg = new Registration();
        reg.setId(55L);
        reg.setPatientId(1L);
        reg.setScheduleId(9L);
        reg.setStatus(BizStatus.REG_REGISTERED);
        Schedule current = bookableSchedule();
        Schedule target = bookableSchedule();
        target.setId(12L);
        target.setRemainingCount(0);
        when(registrationMapper.selectByIdForUpdate(55L)).thenReturn(reg);
        when(scheduleMapper.selectByIdForUpdate(9L)).thenReturn(current);
        when(scheduleMapper.selectByIdForUpdate(12L)).thenReturn(target);

        BusinessException error = assertThrows(BusinessException.class, () -> service.reschedule(55L, 12L));

        assertEquals("目标号源已满", error.getMessage());
        verify(scheduleMapper, never()).decrementRemaining(anyLong());
        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }
}
