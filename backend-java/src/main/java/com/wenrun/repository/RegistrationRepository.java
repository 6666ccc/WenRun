package com.wenrun.repository;

import com.wenrun.entity.Registration;
import com.wenrun.vo.RegistrationVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface RegistrationRepository {

    List<RegistrationVO> selectList(@Param("patientId") Long patientId,
                                  @Param("userId") Long userId,
                                  @Param("registrantUserId") Long registrantUserId,
                                  @Param("staffId") Long staffId,
                                  @Param("status") Integer status);

    Registration selectById(@Param("id") Long id);

    int insert(Registration registration);

    int updateStatus(@Param("id") Long id, @Param("status") Integer status);

    /** 统计患者在指定排班下的有效挂号数（已挂号状态） */
    int countActiveByPatientAndSchedule(@Param("patientId") Long patientId,
                                        @Param("scheduleId") Long scheduleId,
                                        @Param("status") Integer status);
}
