package com.wenrun.service;

import com.wenrun.dto.VisitUpdateDTO;
import com.wenrun.vo.VisitVO;

import java.util.List;

public interface VisitService {
    List<VisitVO> list(Integer status, Long staffId);

    default List<VisitVO> list(Integer status, Long staffId, Long patientId) {
        return list(status, staffId);
    }
    VisitVO getById(Long id);
    Long startVisit(Long registrationId);
    void updateVisit(Long id, VisitUpdateDTO dto);
}
