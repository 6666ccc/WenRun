package com.wenrun.repository;

import com.wenrun.entity.Schedule;
import com.wenrun.vo.ScheduleVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface ScheduleRepository {

    List<ScheduleVO> selectList(@Param("deptId") Long deptId,
                                @Param("workDate") LocalDate workDate,
                                @Param("staffId") Long staffId,
                                @Param("fromDate") LocalDate fromDate);

    ScheduleVO selectVOById(@Param("id") Long id);

    Schedule selectById(@Param("id") Long id);

    Schedule selectByIdForUpdate(@Param("id") Long id);

    int insert(Schedule schedule);

    int updateById(Schedule schedule);

    int decrementRemaining(@Param("id") Long id);

    int incrementRemaining(@Param("id") Long id);
}
