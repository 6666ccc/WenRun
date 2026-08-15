package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
import com.wenrun.dto.PrescriptionCreateDTO;
import com.wenrun.dto.PrescriptionItemDTO;
import com.wenrun.entity.Drug;
import com.wenrun.entity.OutpatientVisit;
import com.wenrun.entity.Prescription;
import com.wenrun.entity.PrescriptionItem;
import com.wenrun.repository.DrugRepository;
import com.wenrun.repository.OutpatientVisitRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.PrescriptionItemRepository;
import com.wenrun.repository.PrescriptionRepository;
import com.wenrun.service.PrescriptionService;
import com.wenrun.service.support.CurrentStaffSupport;
import com.wenrun.vo.PrescriptionVO;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 处方服务实现 — 开方、查询与作废
 */
@Service
@RequiredArgsConstructor
public class PrescriptionServiceImpl implements PrescriptionService {

    private final PrescriptionRepository prescriptionMapper;
    private final PrescriptionItemRepository prescriptionItemMapper;
    private final OutpatientVisitRepository visitMapper;
    private final DrugRepository drugMapper;
    private final PatientRepository patientMapper;
    private final CurrentStaffSupport currentStaffSupport;

    /** 查询某次就诊下的所有处方 */
    @Override
    public List<PrescriptionVO> listByVisit(Long visitId) {
        return prescriptionMapper.selectByVisitId(visitId).stream()
                .map(this::toVo)
                .toList();
    }

    /** 查询已缴费、待发药的处方列表 */
    @Override
    public List<PrescriptionVO> listPendingDispense() {
        return prescriptionMapper.selectByStatus(BizStatus.RX_PAID).stream()
                .map(this::toVo)
                .toList();
    }

    /** 根据 ID 查询处方详情（含明细） */
    @Override
    public PrescriptionVO getById(Long id) {
        Prescription rx = prescriptionMapper.selectById(id);
        if (rx == null) {
            throw new BusinessException("处方不存在");
        }
        return toVo(rx);
    }

    /** 为就诊开具处方，计算金额并写入明细 */
    @Override
    @Transactional
    public Long create(PrescriptionCreateDTO dto) {
        OutpatientVisit visit = visitMapper.selectById(dto.getVisitId());
        if (visit == null) {
            throw new BusinessException("就诊记录不存在");
        }
        currentStaffSupport.assertOwnsStaff(visit.getStaffId());
        BigDecimal total = BigDecimal.ZERO;
        List<PrescriptionItem> items = new ArrayList<>();
        for (PrescriptionItemDTO itemDto : dto.getItems()) {
            Drug drug = drugMapper.selectById(itemDto.getDrugId());
            if (drug == null || drug.getStatus() != BizStatus.ENABLED) {
                throw new BusinessException("药品不可用: " + itemDto.getDrugId());
            }
            BigDecimal amount = drug.getPrice().multiply(itemDto.getQuantity());
            total = total.add(amount);
            PrescriptionItem item = new PrescriptionItem();
            item.setDrugId(drug.getId());
            item.setQuantity(itemDto.getQuantity());
            item.setUnitPrice(drug.getPrice());
            item.setAmount(amount);
            item.setUsageDesc(itemDto.getUsageDesc());
            items.add(item);
        }
        Prescription rx = new Prescription();
        rx.setRxNo(BizNoUtil.next("RX"));
        rx.setVisitId(visit.getId());
        rx.setPatientId(visit.getPatientId());
        rx.setStaffId(visit.getStaffId() != null ? visit.getStaffId() : UserContext.getUserId());
        rx.setTotalAmount(total);
        rx.setStatus(BizStatus.RX_PENDING_PAY);
        prescriptionMapper.insert(rx);
        for (PrescriptionItem item : items) {
            item.setPrescriptionId(rx.getId());
        }
        prescriptionItemMapper.insertBatch(items);
        return rx.getId();
    }

    /** 作废待缴费处方 */
    @Override
    public void cancel(Long id) {
        Prescription rx = prescriptionMapper.selectById(id);
        if (rx == null) {
            throw new BusinessException("处方不存在");
        }
        if (rx.getStatus() != BizStatus.RX_PENDING_PAY) {
            throw new BusinessException("仅待缴费处方可作废");
        }
        OutpatientVisit visit = visitMapper.selectById(rx.getVisitId());
        if (visit == null) {
            throw new BusinessException("就诊记录不存在");
        }
        currentStaffSupport.assertOwnsStaff(visit.getStaffId());
        prescriptionMapper.updateStatus(id, BizStatus.RX_CANCELLED);
    }

    private PrescriptionVO toVo(Prescription rx) {
        PrescriptionVO vo = new PrescriptionVO();
        BeanUtils.copyProperties(rx, vo);
        var patient = patientMapper.selectById(rx.getPatientId());
        if (patient != null) {
            vo.setPatientName(patient.getName());
        }
        vo.setItems(prescriptionItemMapper.selectByPrescriptionId(rx.getId()));
        return vo;
    }
}
