package com.wenrun.repository;

import com.wenrun.ai.vo.PatientClinicalSource;
import com.wenrun.dto.PatientQueryDTO;
import com.wenrun.entity.Patient;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PatientRepository {

    List<Patient> selectByCondition(PatientQueryDTO query);

    Patient selectById(@Param("id") Long id);

    /** 临床上下文专用。SQL 不选择证件、电话、地址、姓名和患者编号。 */
    PatientClinicalSource selectClinicalSource(@Param("id") Long id);

    Patient selectByUserId(@Param("userId") Long userId);

    int insert(Patient patient);

    int updateById(Patient patient);
}
