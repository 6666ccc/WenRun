package com.wenrun.service;

import com.wenrun.dto.ChargePayDTO;
import com.wenrun.vo.ChargeOrderVO;

import java.util.List;

public interface ChargeService {
    List<ChargeOrderVO> list(Integer payStatus, Long patientId);
    ChargeOrderVO getById(Long id);
    Long createFromVisit(Long visitId);
    void pay(Long orderId, ChargePayDTO dto);
}
