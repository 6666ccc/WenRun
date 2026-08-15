package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class ChargeDetail {
    private Long id;
    private Long chargeOrderId;
    private Integer bizType;
    private Long bizId;
    private String itemName;
    private BigDecimal amount;
}
