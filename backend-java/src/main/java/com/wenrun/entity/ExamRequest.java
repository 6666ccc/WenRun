package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class ExamRequest {
    private Long id;
    private String requestNo;
    private Long visitId;
    private Long patientId;
    private Long itemId;
    private BigDecimal amount;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
