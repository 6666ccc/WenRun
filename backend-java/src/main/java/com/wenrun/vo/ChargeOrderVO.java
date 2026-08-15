package com.wenrun.vo;

import com.wenrun.entity.ChargeDetail;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class ChargeOrderVO {
    private Long id;
    private String orderNo;
    private Long patientId;
    private String patientName;
    private Long visitId;
    private BigDecimal totalAmount;
    private BigDecimal paidAmount;
    private Integer payType;
    private Integer payStatus;
    private LocalDateTime payTime;
    private LocalDateTime createTime;
    private List<ChargeDetail> details;
}
