package com.wenrun.service.impl;

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

    /** 按科室、日期、医生查询排班列表 */
    @Override
    public List<ScheduleVO> list(Long deptId, LocalDate workDate, Long staffId) {
        return scheduleMapper.selectList(deptId, workDate, staffId);
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
        if (schedule.getRemainingCount() == null) {
            schedule.setRemainingCount(schedule.getTotalCount());
        }
        scheduleMapper.insert(schedule);
        return schedule.getId();
    }

    /** 更新排班信息 */
    @Override
    public void update(Schedule schedule) {
        getById(schedule.getId());
        scheduleMapper.updateById(schedule);
    }
}
