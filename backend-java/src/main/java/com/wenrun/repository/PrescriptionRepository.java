package com.wenrun.repository;

import com.wenrun.entity.Prescription;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface PrescriptionRepository {

    List<Prescription> selectByVisitId(@Param("visitId") Long visitId);

    List<Prescription> selectPendingByVisitId(@Param("visitId") Long visitId, @Param("status") Integer status);

    List<Prescription> selectByStatus(@Param("status") Integer status);

    Prescription selectById(@Param("id") Long id);

    int insert(Prescription prescription);

    int updateStatus(@Param("id") Long id, @Param("status") Integer status);

    int updateStatusIfCurrent(@Param("id") Long id, @Param("fromStatus") Integer fromStatus,
                              @Param("toStatus") Integer toStatus);

    int updateStatusByVisitId(@Param("visitId") Long visitId,
                              @Param("fromStatus") Integer fromStatus,
                              @Param("toStatus") Integer toStatus);
}
