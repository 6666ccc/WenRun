package com.wenrun.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class PrescriptionItemDTO {
    @NotNull
    private Long drugId;
    @NotNull
    private BigDecimal quantity;
    private String usageDesc;
}
