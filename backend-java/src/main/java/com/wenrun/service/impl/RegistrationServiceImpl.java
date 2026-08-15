package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
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
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class RegistrationServiceImpl implements RegistrationService {

    private final RegistrationRepository registrationMapper;
    private final ScheduleRepository scheduleMapper;
    private final PatientRepository patientMapper;

    //获取用户挂号的信息
    @Override
    public List<RegistrationVO> list(Long patientId, Long userId, Long registrantUserId, Long staffId, Integer status) {

        //获取患者所有的挂号记录
        List<RegistrationVO> registrationVOList = registrationMapper.selectList(
                patientId, userId, registrantUserId, staffId, status);

        //判断当前患者挂号是否过期,如果过期则自动更新数据库状态为已退号
        //1.获取当前日期和时间
        LocalDate today = LocalDate.now();
        LocalTime nowTime = LocalTime.now();
        //2.遍历患者挂号的信息并判断就诊时间是否已过
        for (RegistrationVO registrationVO : registrationVOList){
            //只处理"已挂号"状态的记录
            if (registrationVO.getStatus() == null || registrationVO.getStatus() != BizStatus.REG_REGISTERED) {
                continue;
            }
            //判断就诊时间是否已过
            if (isExpired(registrationVO.getWorkDate(), registrationVO.getTimePeriod(), today, nowTime)) {
                registrationVO.setStatus(BizStatus.REG_CANCELLED);
                //更新数据库挂号单状态
                registrationMapper.updateStatus(registrationVO.getId(), BizStatus.REG_CANCELLED);
            }
        }


        return registrationVOList;

    }

    /**
     * 判断挂号是否已过期
     * @param workDate   就诊日期
     * @param timePeriod 就诊时段（上午/下午/晚上）
     * @param today      当前日期
     * @param nowTime    当前时间
     * @return true=已过期
     */
    private boolean isExpired(LocalDate workDate, String timePeriod, LocalDate today, LocalTime nowTime) {
        if (workDate == null) {
            return false;
        }
        // 就诊日期在今天之前 → 已过期
        if (workDate.isBefore(today)) {
            return true;
        }
        // 就诊日期在今天之后 → 未过期
        if (workDate.isAfter(today)) {
            return false;
        }
        // 同一天：根据就诊时段判断
        if (timePeriod == null) {
            return false;
        }
        switch (timePeriod) {
            case "上午":
                return nowTime.isAfter(LocalTime.of(12, 0));
            case "下午":
                return nowTime.isAfter(LocalTime.of(18, 0));
            case "晚上":
                return nowTime.isAfter(LocalTime.of(21, 0));
            default:
                return false;
        }
    }

    // 挂号
    @Override
    @Transactional
    public Long register(RegistrationCreateDTO dto) {
        Patient patient = patientMapper.selectById(dto.getPatientId());
        if (patient == null) {
            throw new BusinessException("患者不存在");
        }
        Schedule schedule = scheduleMapper.selectByIdForUpdate(dto.getScheduleId());
        if (schedule == null) {
            throw new BusinessException("排班不存在");
        }
        if (schedule.getRemainingCount() == null || schedule.getRemainingCount() <= 0) {
            throw new BusinessException("号源已满");
        }
        int updated = scheduleMapper.decrementRemaining(schedule.getId());
        if (updated == 0) {
            throw new BusinessException("号源扣减失败，请重试");
        }
        Registration reg = new Registration();
        reg.setRegNo(BizNoUtil.next("REG"));
        reg.setPatientId(dto.getPatientId());
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
        registrationMapper.updateStatus(id, BizStatus.REG_CANCELLED);
        scheduleMapper.incrementRemaining(reg.getScheduleId());
    }
}
