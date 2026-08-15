package com.wenrun.vo;

import lombok.Data;

import java.math.BigDecimal;

@Data
public class DrugStockVO {
    private Long drugId;
    private String drugCode;
    private String drugName;
    private String spec;
    private String unit;
    private BigDecimal quantity;
    private BigDecimal warnQuantity;
    private boolean lowStock;
}
