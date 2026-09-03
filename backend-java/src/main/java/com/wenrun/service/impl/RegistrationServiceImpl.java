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
import com.wenrun.service.RegistrationService;
import com.wenrun.vo.RegistrationVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class RegistrationServiceImpl implements RegistrationService {

    private final RegistrationRepository registrationMapper;
    private final ScheduleRepository scheduleMapper;
    private final PatientRepository patientMapper;
    private final ClinicProperties clinicProperties;

    //获取用户挂号的信息
    @Override
    public List<RegistrationVO> list(Long patientId, Long userId, Long registrantUserId, Long staffId, Integer status) {

        // 患者端的数据范围由登录态决定，不能信任前端传入的 patientId/userId。
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            patientId = currentPatientId();
            userId = null;
            registrantUserId = null;
            staffId = null;
        }

        //获取患者所有的挂号记录
        List<RegistrationVO> registrationVOList = registrationMapper.selectList(
                patientId, userId, registrantUserId, staffId, status);

        //判断当前患者挂号是否过期,如果过期则自动更新数据库状态为已退号
        for (RegistrationVO registrationVO : registrationVOList){
            //只处理"已挂号"状态的记录
            if (registrationVO.getStatus() == null || registrationVO.getStatus() != BizStatus.REG_REGISTERED) {
                continue;
            }
            if (clinicProperties.isExpired(registrationVO.getWorkDate(), registrationVO.getTimePeriod())) {
                registrationVO.setStatus(BizStatus.REG_CANCELLED);
                registrationMapper.updateStatus(registrationVO.getId(), BizStatus.REG_CANCELLED);
            }
        }


        return registrationVOList;

    }

    // 挂号
    @Override
    @Transactional
    public Long register(RegistrationCreateDTO dto) {
        Long patientId = dto.getPatientId();
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            patientId = currentPatientId();
        }
        Patient patient = patientMapper.selectById(patientId);
        if (patient == null) {
            throw new BusinessException("患者不存在");
        }
        Schedule schedule = scheduleMapper.selectByIdForUpdate(dto.getScheduleId());
        if (schedule == null) {
            throw new BusinessException("排班不存在");
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
        registrationMapper.insert(reg);
        return reg.getId();
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
        if (AccountType.PATIENT.equals(UserContext.getAccountType())
                && !reg.getPatientId().equals(currentPatientId())) {
            throw new BusinessException("无权操作该挂号单");
        }
        registrationMapper.updateStatus(id, BizStatus.REG_CANCELLED);
        scheduleMapper.incrementRemaining(reg.getScheduleId());
    }

    private Long currentPatientId() {
        Patient patient = patientMapper.selectByUserId(UserContext.getUserId());
        if (patient == null) {
            throw new BusinessException("患者档案不存在");
        }
        return patient.getId();
    }
}
