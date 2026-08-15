package com.wenrun.repository;

import com.wenrun.entity.Dept;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface DeptRepository {

    List<Dept> selectAll(@Param("status") Integer status);

    Dept selectById(@Param("id") Long id);

    int insert(Dept dept);

    int updateById(Dept dept);
}
