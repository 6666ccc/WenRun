package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
import com.wenrun.dto.ExamRequestCreateDTO;
import com.wenrun.entity.ExamRequest;
import com.wenrun.entity.MedicalItem;
import com.wenrun.entity.OutpatientVisit;
import com.wenrun.repository.ExamRequestRepository;
import com.wenrun.repository.MedicalItemRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.OutpatientVisitRepository;
import com.wenrun.service.ExamService;
import com.wenrun.service.support.CurrentStaffSupport;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 检查申请服务实现 — 医生开具检查单
 */
@Service
@RequiredArgsConstructor
public class ExamServiceImpl implements ExamService {

    private final ExamRequestRepository examRequestMapper;
    private final OutpatientVisitRepository visitMapper;
    private final MedicalItemRepository medicalItemMapper;
    private final PatientRepository patientMapper;
    private final CurrentStaffSupport currentStaffSupport;

    /** 查询某次就诊下的检查申请列表 */
    @Override
    public List<ExamRequest> listByVisit(Long visitId) {
        OutpatientVisit visit = visitMapper.selectById(visitId);
        if (visit == null) {
            throw new BusinessException("就诊记录不存在");
        }
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            var patient = patientMapper.selectByUserId(UserContext.getUserId());
            if (patient == null || !patient.getId().equals(visit.getPatientId())) {
                throw new BusinessException("无权查看该检查申请");
            }
        } else {
            currentStaffSupport.assertOwnsStaff(visit.getStaffId());
        }
        return examRequestMapper.selectByVisitId(visitId);
    }

    /** 为就诊创建检查申请，状态为待缴费 */
    @Override
    public Long create(ExamRequestCreateDTO dto) {
        OutpatientVisit visit = visitMapper.selectById(dto.getVisitId());
        if (visit == null) {
            throw new BusinessException("就诊记录不存在");
        }
        currentStaffSupport.assertOwnsStaff(visit.getStaffId());
        MedicalItem item = medicalItemMapper.selectById(dto.getItemId());
        if (item == null || item.getStatus() != BizStatus.ENABLED) {
            throw new BusinessException("诊疗项目不可用");
        }
        ExamRequest request = new ExamRequest();
        request.setRequestNo(BizNoUtil.next("EX"));
        request.setVisitId(visit.getId());
        request.setPatientId(visit.getPatientId());
        request.setItemId(item.getId());
        request.setAmount(item.getPrice());
        request.setStatus(BizStatus.EXAM_PENDING_PAY);
        examRequestMapper.insert(request);
        return request.getId();
    }
}
