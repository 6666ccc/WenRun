package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class DrugStock {
    private Long id;
    private Long drugId;
    private BigDecimal quantity;
    private BigDecimal warnQuantity;
    private LocalDateTime updateTime;
}
