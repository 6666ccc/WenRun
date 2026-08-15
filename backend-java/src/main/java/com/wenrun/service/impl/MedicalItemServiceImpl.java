package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.MedicalItem;
import com.wenrun.repository.MedicalItemRepository;
import com.wenrun.service.MedicalItemService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.List;

/**
 * 诊疗项目服务实现 — 检查/治疗等项目维护
 */
@Service
@RequiredArgsConstructor
public class MedicalItemServiceImpl implements MedicalItemService {

    private final MedicalItemRepository medicalItemMapper;

    /** 按类型与状态查询诊疗项目列表 */
    @Override
    public List<MedicalItem> list(Integer itemType, Integer status) {
        return medicalItemMapper.selectList(itemType, status);
    }

    /** 根据 ID 查询诊疗项目 */
    @Override
    public MedicalItem getById(Long id) {
        MedicalItem item = medicalItemMapper.selectById(id);
        if (item == null) {
            throw new BusinessException("诊疗项目不存在");
        }
        return item;
    }

    /** 新建诊疗项目 */
    @Override
    public Long create(MedicalItem item) {
        if (item.getStatus() == null) {
            item.setStatus(BizStatus.ENABLED);
        }
        if (item.getPrice() == null) {
            item.setPrice(BigDecimal.ZERO);
        }
        medicalItemMapper.insert(item);
        return item.getId();
    }

    /** 更新诊疗项目 */
    @Override
    public void update(MedicalItem item) {
        getById(item.getId());
        medicalItemMapper.updateById(item);
    }
}
