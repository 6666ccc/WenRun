package com.wenrun.service;

import com.wenrun.dto.ExamRequestCreateDTO;
import com.wenrun.entity.ExamRequest;

import java.util.List;

public interface ExamService {
    List<ExamRequest> listByVisit(Long visitId);
    Long create(ExamRequestCreateDTO dto);
}
