package com.wenrun.repository;

import com.wenrun.entity.UserPatientRelation;
import com.wenrun.vo.AccessiblePatientVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface UserPatientRelationRepository {

    UserPatientRelation selectByUserIdAndPatientId(@Param("userId") Long userId,
                                                   @Param("patientId") Long patientId);

    UserPatientRelation selectActive(@Param("userId") Long userId,
                                     @Param("patientId") Long patientId);

    List<AccessiblePatientVO> selectAccessibleByUserId(@Param("userId") Long userId);

    int countActiveByUserId(@Param("userId") Long userId);

    int insert(UserPatientRelation relation);
}
