package com.wenrun.repository;

import com.wenrun.entity.OutpatientVisit;
import com.wenrun.vo.VisitVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface OutpatientVisitRepository {

    List<VisitVO> selectList(@Param("status") Integer status, @Param("staffId") Long staffId);

    OutpatientVisit selectById(@Param("id") Long id);

    VisitVO selectVoById(@Param("id") Long id);

    OutpatientVisit selectByRegistrationId(@Param("registrationId") Long registrationId);

    int insert(OutpatientVisit visit);

    int updateById(OutpatientVisit visit);
}
