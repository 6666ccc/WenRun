package com.wenrun.repository;

import com.wenrun.entity.PatientHealthProfile;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface PatientHealthProfileRepository {

    PatientHealthProfile selectByPatientId(@Param("patientId") Long patientId);

    int insert(PatientHealthProfile profile);

    int updateById(PatientHealthProfile profile);

    int deleteByPatientId(@Param("patientId") Long patientId);
}
