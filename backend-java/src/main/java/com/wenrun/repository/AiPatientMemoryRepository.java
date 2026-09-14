package com.wenrun.repository;

import com.wenrun.entity.AiPatientMemory;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface AiPatientMemoryRepository {
    int insert(AiPatientMemory memory);

    List<AiPatientMemory> selectActiveByPatientId(@Param("patientId") Long patientId,
                                                   @Param("limit") int limit);

    List<AiPatientMemory> selectLatestByPatientId(@Param("patientId") Long patientId,
                                                   @Param("offset") int offset,
                                                   @Param("limit") int limit);

    AiPatientMemory selectLatestForUpdate(@Param("patientId") Long patientId,
                                          @Param("memoryId") String memoryId);

    int markSuperseded(@Param("patientId") Long patientId,
                       @Param("memoryId") String memoryId,
                       @Param("version") Integer version);

    int activatePending(@Param("patientId") Long patientId,
                        @Param("memoryId") String memoryId,
                        @Param("version") Integer version);

    int softDeleteCurrent(@Param("patientId") Long patientId,
                          @Param("memoryId") String memoryId);
}
