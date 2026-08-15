package com.wenrun.repository;

import com.wenrun.entity.ChargeOrder;
import com.wenrun.vo.ChargeOrderVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ChargeOrderRepository {

    List<ChargeOrderVO> selectList(@Param("payStatus") Integer payStatus, @Param("patientId") Long patientId);

    ChargeOrder selectById(@Param("id") Long id);

    ChargeOrderVO selectVoById(@Param("id") Long id);

    int insert(ChargeOrder order);

    int updatePay(ChargeOrder order);
}
