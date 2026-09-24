package com.wenrun.repository;

import com.wenrun.entity.PatientSleepRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface PatientSleepRecordRepository {

    PatientSleepRecord selectByIdAndPatientId(@Param("id") Long id, @Param("patientId") Long patientId);

    List<PatientSleepRecord> selectRecent(@Param("patientId") Long patientId, @Param("limit") int limit);

    List<PatientSleepRecord> selectSince(@Param("patientId") Long patientId, @Param("fromTime") LocalDateTime fromTime);

    int insert(PatientSleepRecord record);

    int updateByIdAndPatientId(PatientSleepRecord record);

    int softDeleteByIdAndPatientId(@Param("id") Long id, @Param("patientId") Long patientId);
}
