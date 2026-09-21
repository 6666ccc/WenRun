package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 账号与患者的授权关系，对应表 user_patient_relation。
 * user_id 是操作者，patient_id 是医疗主体；二者不可互换。
 */
@Data
public class UserPatientRelation {

    private Long id;
    private Long userId;
    private Long patientId;
    private String relationType;
    private Integer isDefault;
    private Integer status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
