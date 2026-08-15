package com.wenrun.service;

import com.wenrun.entity.Staff;
import com.wenrun.vo.StaffVO;

import java.util.List;

public interface StaffService {
    List<StaffVO> list(Long deptId, Integer status);
    Staff getById(Long id);
    Long create(Staff staff);
    void update(Staff staff);
}
