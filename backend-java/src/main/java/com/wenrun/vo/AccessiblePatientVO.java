package com.wenrun.vo;

import lombok.Data;

/**
 * 当前登录账号可管理的患者。
 */
@Data
public class AccessiblePatientVO {

    private Long patientId;
    private String patientNo;
    private String name;
    private String relationType;
    private Boolean isDefault;
}
