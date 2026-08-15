package com.wenrun.repository;

import com.wenrun.entity.DrugStock;
import com.wenrun.vo.DrugStockVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.math.BigDecimal;
import java.util.List;

@Mapper
public interface DrugStockRepository {

    List<DrugStockVO> selectList(@Param("lowStockOnly") Boolean lowStockOnly);

    DrugStock selectByDrugId(@Param("drugId") Long drugId);

    DrugStock selectByDrugIdForUpdate(@Param("drugId") Long drugId);

    int insert(DrugStock stock);

    int deductQuantity(@Param("drugId") Long drugId, @Param("qty") BigDecimal qty);

    long countLowStock();
}
