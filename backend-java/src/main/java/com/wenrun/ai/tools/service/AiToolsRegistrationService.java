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
import com.wenrun.util.BizNoUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class AiToolsRegistrationService {

    private final RegistrationRepository registrationRepository;
    private final ScheduleRepository scheduleRepository;
    private final PatientRepository patientRepository;

    @Transactional
    public Long register(AiToolRegistrationCreateDTO dto, AiDelegationClaims claims) {
        requireScope(claims, "registration:create");
        if (dto.patientId() != null && !dto.patientId().equals(claims.patientId())) {
            throw new AiToolException("INVALID_PATIENT", "patientId must match the delegated patient");
        }
        if (!StringUtils.hasText(claims.interruptId())
                || !claims.interruptId().equals(dto.interruptId())) {
            throw new AiToolException("INTERRUPT_MISMATCH", "interruptId does not match the delegated token");
        }
        if (!StringUtils.hasText(dto.idempotencyKey())) {
            throw new AiToolException("INVALID_IDEMPOTENCY_KEY", "idempotencyKey is required");
        }

        Registration existing = registrationRepository.selectByIdempotencyKey(dto.idempotencyKey());
        if (existing != null) {
            return existing.getId();
        }

        Long patientId = claims.patientId();
        Patient patient = patientRepository.selectById(patientId);
        if (patient == null) {
            throw new AiToolException("INVALID_PATIENT", "patient does not exist");
        }
        if (registrationRepository.countActiveByPatientAndSchedule(
                patientId, dto.scheduleId(), BizStatus.REG_REGISTERED) > 0) {
            throw new AiToolException("DUPLICATE_REGISTRATION", "active registration already exists");
        }

        Schedule schedule = scheduleRepository.selectByIdForUpdate(dto.scheduleId());
        if (schedule == null) {
            throw new AiToolException("SCHEDULE_NOT_FOUND", "schedule not found");
        }
        if (schedule.getRemainingCount() == null || schedule.getRemainingCount() <= 0) {
            throw new AiToolException("SLOT_SOLD_OUT", "no remaining slots");
        }
        int updated = scheduleRepository.decrementRemaining(schedule.getId());
        if (updated == 0) {
            throw new AiToolException("SLOT_SOLD_OUT", "failed to reserve slot");
        }

        Registration registration = new Registration();
        registration.setRegNo(BizNoUtil.next("REG"));
        registration.setPatientId(patientId);
        registration.setScheduleId(schedule.getId());
        registration.setDeptId(schedule.getDeptId());
        registration.setStaffId(schedule.getStaffId());
        registration.setRegTime(LocalDateTime.now());
        registration.setRegFee(schedule.getRegisterFee());
        registration.setStatus(BizStatus.REG_REGISTERED);
        registration.setCashierId(claims.userId());
        registration.setRegistrantUserId(claims.userId());
        registration.setIdempotencyKey(dto.idempotencyKey());
        registrationRepository.insert(registration);
        return registration.getId();
    }

    public static void requireScope(AiDelegationClaims claims, String scope) {
        List<String> scopes = claims == null ? List.of() : claims.scopes();
        if (scopes == null || !scopes.contains(scope)) {
            throw new AiToolException("INSUFFICIENT_SCOPE", "missing required scope: " + scope);
        }
    }
}
