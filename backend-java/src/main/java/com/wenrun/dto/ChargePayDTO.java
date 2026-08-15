package com.wenrun.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.DecimalMin;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class ChargePayDTO {
    @NotNull
    private Integer payType;
    @NotNull
    @DecimalMin(value = "0.01")
    private BigDecimal paidAmount;
}
