package com.wenrun.repository;

import com.wenrun.entity.Registration;
import com.wenrun.vo.RegistrationVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDate;
import java.util.List;

@Mapper
public interface RegistrationRepository {

    List<RegistrationVO> selectList(@Param("patientId") Long patientId,
                                  @Param("registrantUserId") Long registrantUserId,
                                  @Param("staffId") Long staffId,
                                  @Param("status") Integer status);

    Registration selectById(@Param("id") Long id);

    Registration selectByIdForUpdate(@Param("id") Long id);

    int insert(Registration registration);

    int updateStatus(@Param("id") Long id, @Param("status") Integer status);

    /** 仅当当前状态等于 expectedStatus 时才流转；返回受影响行数，用于判断本次调用是否真正生效。 */
    int updateStatusIfCurrent(@Param("id") Long id,
                              @Param("expectedStatus") Integer expectedStatus,
                              @Param("status") Integer status);

    /** 统计患者在指定排班下的有效挂号数（已挂号状态） */
    int countActiveByPatientAndSchedule(@Param("patientId") Long patientId,
                                        @Param("scheduleId") Long scheduleId,
                                        @Param("status") Integer status);

    /** 统计患者对同一医生、同一天、同一时段的有效挂号（已挂号/已就诊） */
    int countActiveByPatientAndSlot(@Param("patientId") Long patientId,
                                    @Param("staffId") Long staffId,
                                    @Param("workDate") LocalDate workDate,
                                    @Param("timePeriod") String timePeriod);

    int countOtherActiveByPatientAndSlot(@Param("patientId") Long patientId,
                                         @Param("staffId") Long staffId,
                                         @Param("workDate") LocalDate workDate,
                                         @Param("timePeriod") String timePeriod,
                                         @Param("excludeRegistrationId") Long excludeRegistrationId);

    int updateScheduleIfCurrent(@Param("id") Long id,
                                @Param("expectedScheduleId") Long expectedScheduleId,
                                @Param("expectedStatus") Integer expectedStatus,
                                @Param("scheduleId") Long scheduleId,
                                @Param("deptId") Long deptId,
                                @Param("staffId") Long staffId,
                                @Param("regFee") java.math.BigDecimal regFee);

    Registration selectByIdempotencyKey(@Param("idempotencyKey") String idempotencyKey);
}
