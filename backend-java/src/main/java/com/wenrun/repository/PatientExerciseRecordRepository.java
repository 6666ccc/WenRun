package com.wenrun.repository;

import com.wenrun.entity.PatientExerciseRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface PatientExerciseRecordRepository {

    PatientExerciseRecord selectByIdAndPatientId(@Param("id") Long id, @Param("patientId") Long patientId);

    List<PatientExerciseRecord> selectRecent(@Param("patientId") Long patientId, @Param("limit") int limit);

    List<PatientExerciseRecord> selectSince(@Param("patientId") Long patientId, @Param("fromTime") LocalDateTime fromTime);

    int insert(PatientExerciseRecord record);

    int updateByIdAndPatientId(PatientExerciseRecord record);

    int softDeleteByIdAndPatientId(@Param("id") Long id, @Param("patientId") Long patientId);
}
