package com.wenrun.repository;

import com.wenrun.entity.HealthMetricRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface HealthMetricRecordRepository {

    HealthMetricRecord selectByIdAndPatientId(@Param("id") Long id, @Param("patientId") Long patientId);

    List<HealthMetricRecord> selectTrend(@Param("patientId") Long patientId,
                                         @Param("metricType") String metricType,
                                         @Param("fromTime") LocalDateTime fromTime);

    List<HealthMetricRecord> selectRecent(@Param("patientId") Long patientId,
                                          @Param("metricType") String metricType,
                                          @Param("limit") int limit);

    int insert(HealthMetricRecord record);

    int updateByIdAndPatientId(HealthMetricRecord record);

    int softDeleteByIdAndPatientId(@Param("id") Long id, @Param("patientId") Long patientId);
}
