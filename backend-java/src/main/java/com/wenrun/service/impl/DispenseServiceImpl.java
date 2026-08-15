package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.DispenseRecord;
import com.wenrun.entity.DrugStock;
import com.wenrun.entity.Prescription;
import com.wenrun.entity.PrescriptionItem;
import com.wenrun.repository.DispenseRecordRepository;
import com.wenrun.repository.DrugStockRepository;
import com.wenrun.repository.PrescriptionItemRepository;
import com.wenrun.repository.PrescriptionRepository;
import com.wenrun.service.DispenseService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 发药服务实现 — 扣减库存并记录发药
 */
@Service
@RequiredArgsConstructor
public class DispenseServiceImpl implements DispenseService {

    private final PrescriptionRepository prescriptionMapper;
    private final PrescriptionItemRepository prescriptionItemMapper;
    private final DrugStockRepository drugStockMapper;
    private final DispenseRecordRepository dispenseRecordMapper;

    /** 对已缴费处方执行发药：校验库存、扣减数量、写入发药记录 */
    @Override
    @Transactional
    public void dispense(Long prescriptionId) {
        Prescription rx = prescriptionMapper.selectById(prescriptionId);
        if (rx == null) {
            throw new BusinessException("处方不存在");
        }
        if (rx.getStatus() != BizStatus.RX_PAID) {
            throw new BusinessException("处方未缴费，不能发药");
        }
        if (dispenseRecordMapper.selectByPrescriptionId(prescriptionId) != null) {
            throw new BusinessException("处方已发药");
        }
        if (prescriptionMapper.updateStatusIfCurrent(prescriptionId, BizStatus.RX_PAID, BizStatus.RX_DISPENSED) == 0) {
            throw new BusinessException("Prescription already dispensed");
        }
        List<PrescriptionItem> items = prescriptionItemMapper.selectByPrescriptionId(prescriptionId);
        for (PrescriptionItem item : items) {
            DrugStock stock = drugStockMapper.selectByDrugIdForUpdate(item.getDrugId());
            if (stock == null || stock.getQuantity().compareTo(item.getQuantity()) < 0) {
                throw new BusinessException("药品库存不足，drugId=" + item.getDrugId());
            }
            int rows = drugStockMapper.deductQuantity(item.getDrugId(), item.getQuantity());
            if (rows == 0) {
                throw new BusinessException("库存扣减失败");
            }
        }
        DispenseRecord record = new DispenseRecord();
        record.setPrescriptionId(prescriptionId);
        record.setPharmacistId(UserContext.getUserId());
        record.setDispenseTime(LocalDateTime.now());
        record.setStatus(BizStatus.ENABLED);
        dispenseRecordMapper.insert(record);
    }
}
