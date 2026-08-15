package com.wenrun.service;

import com.wenrun.entity.Schedule;
import com.wenrun.vo.ScheduleVO;

import java.time.LocalDate;
import java.util.List;

public interface ScheduleService {
    List<ScheduleVO> list(Long deptId, LocalDate workDate, Long staffId);
    ScheduleVO getDetail(Long id);
    Schedule getById(Long id);
    Long create(Schedule schedule);
    void update(Schedule schedule);
}
