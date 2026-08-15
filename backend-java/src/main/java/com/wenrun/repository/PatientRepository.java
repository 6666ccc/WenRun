package com.wenrun.repository;

import com.wenrun.dto.PatientQueryDTO;
import com.wenrun.entity.Patient;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PatientRepository {

    List<Patient> selectByCondition(PatientQueryDTO query);

    Patient selectById(@Param("id") Long id);

    Patient selectByUserId(@Param("userId") Long userId);

    int insert(Patient patient);

    int updateById(Patient patient);
}
