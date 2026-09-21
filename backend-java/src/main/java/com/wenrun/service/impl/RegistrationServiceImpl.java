package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
import com.wenrun.config.ClinicProperties;
import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.entity.Patient;
import com.wenrun.entity.Registration;
import com.wenrun.entity.Schedule;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.RegistrationRepository;
import com.wenrun.repository.ScheduleRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.service.RegistrationService;
import com.wenrun.vo.RegistrationVO;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

@Service
@RequiredArgsConstructor
public class RegistrationServiceImpl implements RegistrationService {

    private final RegistrationRepository registrationMapper;
    private final ScheduleRepository scheduleMapper;
    private final PatientRepository patientMapper;
    private final ClinicProperties clinicProperties;
    private final PatientAccessService patientAccess;

    @Override
    @Transactional
    public List<RegistrationVO> list(Long patientId, Long registrantUserId, Long staffId, Integer status) {
        if (isPatientAccount()) {
            patientId = patientAccess.resolvePatientId(patientId);
            registrantUserId = null;
            staffId = null;
        }

        List<RegistrationVO> registrationVOList = registrationMapper.selectList(
                patientId, registrantUserId, staffId, status);

        //判断当前患者挂号是否过期,如果过期则自动退号并把号源还回排班
        for (RegistrationVO registrationVO : registrationVOList) {
            //只处理"已挂号"状态的记录
            if (registrationVO.getStatus() == null || registrationVO.getStatus() != BizStatus.REG_REGISTERED) {
                continue;
            }
            if (!clinicProperties.isExpired(registrationVO.getWorkDate(), registrationVO.getTimePeriod())) {
                continue;
            }
            // 条件更新让状态流转本身成为并发仲裁点：只有抢到这次流转的调用才回补号源，
            // 否则两个并发查询会把同一张单的号源加两次。
            boolean transitioned = registrationMapper.updateStatusIfCurrent(
                    registrationVO.getId(), BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED) == 1;
            if (transitioned && registrationVO.getScheduleId() != null) {
                scheduleMapper.incrementRemaining(registrationVO.getScheduleId());
            }
            registrationVO.setStatus(BizStatus.REG_CANCELLED);
        }

        return registrationVOList;
    }

    // 挂号
    @Override
    @Transactional
    public Long register(RegistrationCreateDTO dto) {
        Long patientId = resolveSubjectPatientId(dto.getPatientId());
        Patient patient = patientMapper.selectById(patientId);
        if (patient == null) {
            throw new BusinessException("患者不存在");
        }
        Schedule schedule = scheduleMapper.selectByIdForUpdate(dto.getScheduleId());
        if (schedule == null) {
            throw new BusinessException("排班不存在");
        }

        // 行锁已把同一排班的并发挂号串行化，锁内查询能读到前一笔已提交的重放记录。
        // 幂等命中必须早于过期与号源校验：已经挂上的号在排班过期后被重放时，应当返回原单而不是报错。
        String idempotencyKey = normalizeIdempotencyKey(dto.getIdempotencyKey());
        if (idempotencyKey != null) {
            Registration replayed = registrationMapper.selectByIdempotencyKey(idempotencyKey);
            if (replayed != null) {
                if (!Objects.equals(replayed.getPatientId(), patientId)) {
                    throw new BusinessException("幂等键已被占用，请更换后重试");
                }
                return replayed.getId();
            }
        }

        if (clinicProperties.isExpired(schedule.getWorkDate(), schedule.getTimePeriod())) {
            throw new BusinessException("该排班已过期，无法挂号");
        }
        if (schedule.getRemainingCount() == null || schedule.getRemainingCount() <= 0) {
            throw new BusinessException("号源已满");
        }
        if (registrationMapper.countActiveByPatientAndSlot(
                patientId, schedule.getStaffId(), schedule.getWorkDate(), schedule.getTimePeriod()) > 0) {
            throw new BusinessException("您已预约该医生此时段，不能重复挂号");
        }
        int updated = scheduleMapper.decrementRemaining(schedule.getId());
        if (updated == 0) {
            throw new BusinessException("号源扣减失败，请重试");
        }
        Registration reg = new Registration();
        reg.setRegNo(BizNoUtil.next("REG"));
        reg.setPatientId(patientId);
        reg.setScheduleId(schedule.getId());
        reg.setDeptId(schedule.getDeptId());
        reg.setStaffId(schedule.getStaffId());
        reg.setRegTime(LocalDateTime.now());
        reg.setRegFee(schedule.getRegisterFee());
        reg.setStatus(BizStatus.REG_REGISTERED);
        reg.setCashierId(UserContext.getUserId());
        reg.setRegistrantUserId(UserContext.getUserId());
        reg.setIdempotencyKey(idempotencyKey);
        try {
            registrationMapper.insert(reg);
        } catch (DuplicateKeyException ex) {
            // 同一幂等键指向不同排班时锁的不是同一行，行锁挡不住，由唯一索引兜底。
            throw new BusinessException("请勿重复提交挂号请求");
        }
        return reg.getId();
    }

    /** 空白幂等键归一化为 null，避免多张单共用空串撞唯一索引。 */
    private static String normalizeIdempotencyKey(String raw) {
        if (raw == null) {
            return null;
        }
        String trimmed = raw.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    /**
     * 改约只更换号源，不新建第二张挂号单。先锁挂号单，再按 ID 顺序锁两个号源，
     * 既保证号源回补/占用在同一事务内完成，也避免并发换号时交叉等待。
     */
    @Override
    @Transactional
    public void reschedule(Long id, Long targetScheduleId) {
        if (targetScheduleId == null) {
            throw new BusinessException("目标号源不能为空");
        }
        Registration reg = registrationMapper.selectByIdForUpdate(id);
        if (reg == null) {
            throw new BusinessException("挂号单不存在");
        }
        if (isPatientAccount()) {
            patientAccess.assertAccess(reg.getPatientId());
        }
        if (reg.getStatus() != BizStatus.REG_REGISTERED) {
            throw new BusinessException("只有待就诊挂号可以改约");
        }
        if (Objects.equals(reg.getScheduleId(), targetScheduleId)) {
            return;
        }

        long firstId = Math.min(reg.getScheduleId(), targetScheduleId);
        long secondId = Math.max(reg.getScheduleId(), targetScheduleId);
        Schedule first = scheduleMapper.selectByIdForUpdate(firstId);
        Schedule second = scheduleMapper.selectByIdForUpdate(secondId);
        if (first == null || second == null) {
            throw new BusinessException("号源不存在");
        }
        Schedule current = Objects.equals(first.getId(), reg.getScheduleId()) ? first : second;
        Schedule target = Objects.equals(first.getId(), targetScheduleId) ? first : second;
        if (clinicProperties.isExpired(target.getWorkDate(), target.getTimePeriod())) {
            throw new BusinessException("目标号源已过期，无法改约");
        }
        if (target.getRemainingCount() == null || target.getRemainingCount() <= 0) {
            throw new BusinessException("目标号源已满");
        }
        if (registrationMapper.countOtherActiveByPatientAndSlot(
                reg.getPatientId(), target.getStaffId(), target.getWorkDate(),
                target.getTimePeriod(), reg.getId()) > 0) {
            throw new BusinessException("您已预约该专家此时段，不能重复改约");
        }
        if (scheduleMapper.decrementRemaining(target.getId()) != 1) {
            throw new BusinessException("目标号源状态已变化，请刷新后重试");
        }
        if (registrationMapper.updateScheduleIfCurrent(
                reg.getId(), current.getId(), BizStatus.REG_REGISTERED,
                target.getId(), target.getDeptId(), target.getStaffId(), target.getRegisterFee()) != 1) {
            throw new BusinessException("挂号单状态已变化，请刷新后重试");
        }
        scheduleMapper.incrementRemaining(current.getId());
    }

    // 取消挂号
    @Override
    @Transactional
    public void cancel(Long id) {
        Registration reg = registrationMapper.selectById(id);
        if (reg == null) {
            throw new BusinessException("挂号单不存在");
        }
        if (reg.getStatus() == BizStatus.REG_CANCELLED) {
            throw new BusinessException("挂号单已退号");
        }
        if (reg.getStatus() == BizStatus.REG_VISITED) {
            throw new BusinessException("已就诊不能退号");
        }
        if (isPatientAccount()) {
            patientAccess.assertAccess(reg.getPatientId());
        }
        // 前面的状态判断只为给出友好文案；真正的并发守卫是这次条件更新。
        if (registrationMapper.updateStatusIfCurrent(
                id, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED) != 1) {
            throw new BusinessException("挂号单状态已变化，请刷新后重试");
        }
        scheduleMapper.incrementRemaining(reg.getScheduleId());
    }

    private Long resolveSubjectPatientId(Long requestedPatientId) {
        if (isPatientAccount()) {
            return patientAccess.resolvePatientId(requestedPatientId);
        }
        if (requestedPatientId == null) {
            throw new BusinessException("患者不存在");
        }
        return requestedPatientId;
    }

    private boolean isPatientAccount() {
        return AccountType.PATIENT.equals(UserContext.getAccountType());
    }
}
