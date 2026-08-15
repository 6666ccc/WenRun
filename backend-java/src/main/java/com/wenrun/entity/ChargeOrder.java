package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class ChargeOrder {
    private Long id;
    private String orderNo;
    private Long patientId;
    private Long visitId;
    private BigDecimal totalAmount;
    private BigDecimal paidAmount;
    private Integer payType;
    private Integer payStatus;
    private Long cashierId;
    private LocalDateTime payTime;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
