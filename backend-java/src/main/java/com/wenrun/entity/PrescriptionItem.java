package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class PrescriptionItem {
    private Long id;
    private Long prescriptionId;
    private Long drugId;
    private BigDecimal quantity;
    private BigDecimal unitPrice;
    private BigDecimal amount;
    private String usageDesc;
}
