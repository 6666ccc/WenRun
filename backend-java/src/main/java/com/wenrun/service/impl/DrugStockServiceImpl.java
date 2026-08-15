package com.wenrun.service.impl;

import com.wenrun.repository.DrugStockRepository;
import com.wenrun.service.DrugStockService;
import com.wenrun.vo.DrugStockVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 药品库存服务实现
 */
@Service
@RequiredArgsConstructor
public class DrugStockServiceImpl implements DrugStockService {

    private final DrugStockRepository drugStockMapper;

    /** 查询库存列表，lowStockOnly=true 时仅返回低于预警量的药品 */
    @Override
    public List<DrugStockVO> list(Boolean lowStockOnly) {
        return drugStockMapper.selectList(lowStockOnly);
    }
}
