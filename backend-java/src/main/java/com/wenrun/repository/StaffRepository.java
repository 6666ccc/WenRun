package com.wenrun.repository;

import com.wenrun.entity.Staff;
import com.wenrun.vo.StaffVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface StaffRepository {

    List<StaffVO> selectList(@Param("deptId") Long deptId, @Param("status") Integer status);

    Staff selectById(@Param("id") Long id);

    Staff selectByUserId(@Param("userId") Long userId);

    int insert(Staff staff);

    int updateById(Staff staff);
}
