package com.wenrun.repository;

import com.wenrun.entity.PrescriptionItem;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PrescriptionItemRepository {

    List<PrescriptionItem> selectByPrescriptionId(@Param("prescriptionId") Long prescriptionId);

    int insertBatch(@Param("items") List<PrescriptionItem> items);
}
