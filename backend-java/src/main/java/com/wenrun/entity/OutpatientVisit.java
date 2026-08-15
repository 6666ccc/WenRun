package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class OutpatientVisit {
    private Long id;
    private String visitNo;
    private Long registrationId;
    private Long patientId;
    private Long staffId;
    private LocalDateTime visitTime;
    private String chiefComplaint;
    private String diagnosis;
    private Integer status;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
