package com.wenrun.service;

import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.vo.RegistrationVO;

import java.util.List;

public interface RegistrationService {
    List<RegistrationVO> list(Long patientId, Long registrantUserId, Long staffId, Integer status);
    Long register(RegistrationCreateDTO dto);
    void reschedule(Long id, Long scheduleId);
    void cancel(Long id);
}
