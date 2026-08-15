package com.wenrun.vo;

import com.wenrun.entity.PrescriptionItem;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class PrescriptionVO {
    private Long id;
    private String rxNo;
    private Long visitId;
    private Long patientId;
    private String patientName;
    private BigDecimal totalAmount;
    private Integer status;
    private LocalDateTime createTime;
    private List<PrescriptionItem> items;
}
