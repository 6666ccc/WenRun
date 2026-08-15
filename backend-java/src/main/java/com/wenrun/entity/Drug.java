package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class Drug {
    private Long id;
    private String drugCode;
    private String drugName;
    private String spec;
    private String unit;
    private BigDecimal price;
    private String manufacturer;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
