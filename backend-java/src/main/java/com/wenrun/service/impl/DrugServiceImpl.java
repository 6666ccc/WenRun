package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.Drug;
import com.wenrun.entity.DrugStock;
import com.wenrun.repository.DrugRepository;
import com.wenrun.repository.DrugStockRepository;
import com.wenrun.service.DrugService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

/**
 * 药品服务实现 — 药品维护及初始库存创建
 */
@Service
@RequiredArgsConstructor
public class DrugServiceImpl implements DrugService {

    private final DrugRepository drugMapper;
    private final DrugStockRepository drugStockMapper;

    /** 按关键词与状态查询药品列表 */
    @Override
    public List<Drug> list(String keyword, Integer status) {
        return drugMapper.selectList(keyword, status);
    }

    /** 根据 ID 查询药品 */
    @Override
    public Drug getById(Long id) {
        Drug drug = drugMapper.selectById(id);
        if (drug == null) {
            throw new BusinessException("药品不存在");
        }
        return drug;
    }

    /** 新建药品并初始化默认库存（100 件，预警 10 件） */
    @Override
    @Transactional
    public Long create(Drug drug) {
        if (drug.getStatus() == null) {
            drug.setStatus(BizStatus.ENABLED);
        }
        if (drug.getPrice() == null) {
            drug.setPrice(BigDecimal.ZERO);
        }
        drugMapper.insert(drug);
        DrugStock stock = new DrugStock();
        stock.setDrugId(drug.getId());
        stock.setQuantity(BigDecimal.valueOf(100));
        stock.setWarnQuantity(BigDecimal.valueOf(10));
        drugStockMapper.insert(stock);
        return drug.getId();
    }

    /** 更新药品信息 */
    @Override
    public void update(Drug drug) {
        getById(drug.getId());
        drugMapper.updateById(drug);
    }
}
