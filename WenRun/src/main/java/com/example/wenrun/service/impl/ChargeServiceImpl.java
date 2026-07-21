package com.example.wenrun.service.impl;

import com.example.wenrun.common.constant.AccountType;
import com.example.wenrun.common.constant.BizStatus;
import com.example.wenrun.common.context.UserContext;
import com.example.wenrun.common.exception.BusinessException;
import com.example.wenrun.common.util.BizNoUtil;
import com.example.wenrun.dto.ChargePayDTO;
import com.example.wenrun.entity.ChargeDetail;
import com.example.wenrun.entity.ChargeOrder;
import com.example.wenrun.entity.ExamRequest;
import com.example.wenrun.entity.MedicalItem;
import com.example.wenrun.entity.OutpatientVisit;
import com.example.wenrun.entity.Patient;
import com.example.wenrun.entity.Prescription;
import com.example.wenrun.entity.Registration;
import com.example.wenrun.mapper.ChargeDetailMapper;
import com.example.wenrun.mapper.ChargeOrderMapper;
import com.example.wenrun.mapper.ExamRequestMapper;
import com.example.wenrun.mapper.MedicalItemMapper;
import com.example.wenrun.mapper.OutpatientVisitMapper;
import com.example.wenrun.mapper.PatientMapper;
import com.example.wenrun.mapper.PrescriptionMapper;
import com.example.wenrun.mapper.RegistrationMapper;
import com.example.wenrun.service.ChargeService;
import com.example.wenrun.vo.ChargeOrderVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 收费服务实现 — 生成收费单与收款
 */
@Service
@RequiredArgsConstructor
public class ChargeServiceImpl implements ChargeService {

    private final ChargeOrderMapper chargeOrderMapper;
    private final ChargeDetailMapper chargeDetailMapper;
    private final OutpatientVisitMapper visitMapper;
    private final RegistrationMapper registrationMapper;
    private final PrescriptionMapper prescriptionMapper;
    private final ExamRequestMapper examRequestMapper;
    private final MedicalItemMapper medicalItemMapper;
    private final PatientMapper patientMapper;

    /** 按支付状态与患者查询收费单列表 */
    @Override
    public List<ChargeOrderVO> list(Integer payStatus, Long patientId) {
        if (isPatientAccount()) {
            return chargeOrderMapper.selectList(payStatus, currentPatientId());
        }
        return chargeOrderMapper.selectList(payStatus, patientId);
    }

    /** 查询收费单详情（含明细项） */
    @Override
    public ChargeOrderVO getById(Long id) {
        ChargeOrder order = chargeOrderMapper.selectById(id);
        if (order == null) {
            throw new BusinessException("收费单不存在");
        }
        assertOrderOwnership(order);
        ChargeOrderVO vo = chargeOrderMapper.selectVoById(id);
        if (vo == null) {
            throw new BusinessException("Charge order not found");
        }
        vo.setDetails(chargeDetailMapper.selectByOrderId(id));
        return vo;
    }

    /** 根据就诊记录汇总待收费项（挂号费、处方、检查）并生成收费单 */
    @Override
    @Transactional
    public Long createFromVisit(Long visitId) {
        OutpatientVisit visit = visitMapper.selectById(visitId);
        if (visit == null) {
            throw new BusinessException("就诊记录不存在");
        }
        assertVisitOwnership(visit);
        List<ChargeDetail> details = new ArrayList<>();
        BigDecimal total = BigDecimal.ZERO;

        Registration reg = registrationMapper.selectById(visit.getRegistrationId());
        if (reg != null && chargeDetailMapper.countByBiz(BizStatus.CHARGE_REG, reg.getId()) == 0) {
            ChargeDetail d = new ChargeDetail();
            d.setBizType(BizStatus.CHARGE_REG);
            d.setBizId(reg.getId());
            d.setItemName("挂号费");
            d.setAmount(reg.getRegFee());
            details.add(d);
            total = total.add(reg.getRegFee());
        }

        for (Prescription rx : prescriptionMapper.selectPendingByVisitId(visitId, BizStatus.RX_PENDING_PAY)) {
            if (chargeDetailMapper.countByBiz(BizStatus.CHARGE_RX, rx.getId()) == 0) {
                ChargeDetail d = new ChargeDetail();
                d.setBizType(BizStatus.CHARGE_RX);
                d.setBizId(rx.getId());
                d.setItemName("处方 " + rx.getRxNo());
                d.setAmount(rx.getTotalAmount());
                details.add(d);
                total = total.add(rx.getTotalAmount());
            }
        }

        for (ExamRequest ex : examRequestMapper.selectPendingByVisitId(visitId, BizStatus.EXAM_PENDING_PAY)) {
            if (chargeDetailMapper.countByBiz(BizStatus.CHARGE_EXAM, ex.getId()) == 0) {
                MedicalItem item = medicalItemMapper.selectById(ex.getItemId());
                ChargeDetail d = new ChargeDetail();
                d.setBizType(BizStatus.CHARGE_EXAM);
                d.setBizId(ex.getId());
                d.setItemName(item != null ? item.getItemName() : "检查项目");
                d.setAmount(ex.getAmount());
                details.add(d);
                total = total.add(ex.getAmount());
            }
        }

        if (details.isEmpty()) {
            throw new BusinessException("没有待收费项目");
        }

        ChargeOrder order = new ChargeOrder();
        order.setOrderNo(BizNoUtil.next("CHG"));
        order.setPatientId(visit.getPatientId());
        order.setVisitId(visitId);
        order.setTotalAmount(total);
        order.setPaidAmount(BigDecimal.ZERO);
        order.setPayStatus(BizStatus.PAY_PENDING);
        order.setCashierId(UserContext.getUserId());
        chargeOrderMapper.insert(order);

        for (ChargeDetail d : details) {
            d.setChargeOrderId(order.getId());
        }
        chargeDetailMapper.insertBatch(details);
        return order.getId();
    }

    /** 确认收款，并联动更新处方/检查申请为已缴费 */
    @Override
    @Transactional
    public void pay(Long orderId, ChargePayDTO dto) {
        ChargeOrder order = chargeOrderMapper.selectById(orderId);
        if (order == null) {
            throw new BusinessException("收费单不存在");
        }
        if (order.getPayStatus() != BizStatus.PAY_PENDING) {
            throw new BusinessException("收费单状态不允许支付");
        }
        assertOrderOwnership(order);
        BigDecimal paid = dto.getPaidAmount();
        if (paid == null || paid.compareTo(BigDecimal.ZERO) <= 0 || paid.compareTo(order.getTotalAmount()) != 0) {
            throw new BusinessException("Invalid payment amount");
        }
        order.setPaidAmount(paid);
        order.setPayType(dto.getPayType());
        order.setPayStatus(BizStatus.PAY_PAID);
        order.setCashierId(UserContext.getUserId());
        order.setPayTime(LocalDateTime.now());
        chargeOrderMapper.updatePay(order);

        List<ChargeDetail> details = chargeDetailMapper.selectByOrderId(orderId);
        for (ChargeDetail d : details) {
            if (d.getBizType() == BizStatus.CHARGE_RX) {
                prescriptionMapper.updateStatus(d.getBizId(), BizStatus.RX_PAID);
            } else if (d.getBizType() == BizStatus.CHARGE_EXAM) {
                examRequestMapper.updateStatus(d.getBizId(), BizStatus.EXAM_PAID);
            }
        }
    }

    private boolean isPatientAccount() {
        return AccountType.PATIENT.equals(UserContext.getAccountType());
    }

    private Long currentPatientId() {
        Patient patient = patientMapper.selectByUserId(UserContext.getUserId());
        if (patient == null) throw new BusinessException("Patient profile not found");
        return patient.getId();
    }

    private void assertOrderOwnership(ChargeOrder order) {
        if (isPatientAccount() && !order.getPatientId().equals(currentPatientId())) {
            throw new BusinessException("Access denied");
        }
    }

    private void assertVisitOwnership(OutpatientVisit visit) {
        if (isPatientAccount() && !visit.getPatientId().equals(currentPatientId())) {
            throw new BusinessException("Access denied");
        }
    }
}
