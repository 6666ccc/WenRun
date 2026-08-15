package com.wenrun.repository;

import com.wenrun.entity.DispenseRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface DispenseRecordRepository {

    DispenseRecord selectByPrescriptionId(@Param("prescriptionId") Long prescriptionId);

    int insert(DispenseRecord record);
}
