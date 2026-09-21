package com.wenrun.repository;

import com.wenrun.entity.PatientHealthSnapshot;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PatientHealthSnapshotRepository {

    List<PatientHealthSnapshot> selectByPatientId(@Param("patientId") Long patientId);

    PatientHealthSnapshot selectById(@Param("id") Long id);

    int insert(PatientHealthSnapshot snapshot);

    int deleteById(@Param("id") Long id);
}
