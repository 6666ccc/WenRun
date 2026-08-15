package com.wenrun.dto;

import lombok.Data;

/**
 * 患者查询条件
 */
@Data
public class PatientQueryDTO {

    private String name;
    private String phone;
    private String idCard;
}
