package com.wenrun.entity;

import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
public class AiPatientMemory {
    private Long id;
    private String memoryId;
    private Long patientId;
    private String type;
    private String content;
    private String sourceConversationId;
    private Long sourceMessageId;
    private String status;
    private Integer version;
    private BigDecimal confidence;
    private LocalDateTime expireTime;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private LocalDateTime deletedTime;
}
