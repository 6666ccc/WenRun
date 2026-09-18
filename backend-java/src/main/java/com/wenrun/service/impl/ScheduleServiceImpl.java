package com.wenrun.service.impl;

import com.wenrun.config.ClinicProperties;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.Schedule;
import com.wenrun.repository.ScheduleRepository;
import com.wenrun.service.ScheduleService;
import com.wenrun.vo.ScheduleVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.List;

/**
 * 排班服务实现
 */
@Service
@RequiredArgsConstructor
public class ScheduleServiceImpl implements ScheduleService {

    private final ScheduleRepository scheduleMapper;
    private final ClinicProperties clinicProperties;

    /** 按科室、日期、医生查询排班列表；默认只返回今天及以后、且当前时段尚未截止的号源 */
    @Override
    public List<ScheduleVO> list(Long deptId, LocalDate workDate, Long staffId) {
        LocalDate fromDate = workDate == null ? clinicProperties.today() : null;
        List<ScheduleVO> schedules = scheduleMapper.selectList(deptId, workDate, staffId, fromDate);
        if (schedules == null || schedules.isEmpty()) {
            return List.of();
        }
        return schedules.stream()
                .filter(item -> !clinicProperties.isExpired(item.getWorkDate(), item.getTimePeriod()))
                .toList();
    }

    /** 根据 ID 查询排班（含科室、医生名称） */
    @Override
    public ScheduleVO getDetail(Long id) {
        ScheduleVO schedule = scheduleMapper.selectVOById(id);
        if (schedule == null) {
            throw new BusinessException("排班不存在");
        }
        return schedule;
    }

    /** 根据 ID 查询排班 */
    @Override
    public Schedule getById(Long id) {
        Schedule schedule = scheduleMapper.selectById(id);
        if (schedule == null) {
            throw new BusinessException("排班不存在");
        }
        return schedule;
    }

    /** 新建排班，剩余号源默认等于总号源 */
    @Override
    public Long create(Schedule schedule) {
        requireSlotManager();
        if (schedule.getTotalCount() == null || schedule.getTotalCount() <= 0) {
            throw new BusinessException("总号源必须大于 0");
        }
        if (schedule.getRemainingCount() == null) {
            schedule.setRemainingCount(schedule.getTotalCount());
        }
        scheduleMapper.insert(schedule);
        return schedule.getId();
    }

    /** 更新排班信息 */
    @Override
    public void update(Schedule schedule) {
        requireSlotManager();
        Schedule current = getById(schedule.getId());
        if (schedule.getTotalCount() != null) {
            int bookedCount = current.getTotalCount() - current.getRemainingCount();
            if (schedule.getTotalCount() < bookedCount) {
                throw new BusinessException("总号源不能小于已预约数量");
            }
            schedule.setRemainingCount(schedule.getTotalCount() - bookedCount);
        } else {
            // 剩余号源只能由挂号、改约、取消事务维护，管理接口不能直接覆盖。
            schedule.setRemainingCount(null);
        }
        scheduleMapper.updateById(schedule);
    }

    private static void requireSlotManager() {
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            throw new BusinessException("患者账号无权维护号源");
        }
    }
}
