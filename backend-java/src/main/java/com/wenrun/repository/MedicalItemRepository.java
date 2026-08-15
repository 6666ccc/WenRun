package com.wenrun.repository;

import com.wenrun.entity.MedicalItem;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface MedicalItemRepository {

    List<MedicalItem> selectList(@Param("itemType") Integer itemType, @Param("status") Integer status);

    MedicalItem selectById(@Param("id") Long id);

    int insert(MedicalItem item);

    int updateById(MedicalItem item);
}
