package com.wenrun.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class VisitVO {
    private Long id;
    private String visitNo;
    private Long registrationId;
    private String regNo;
    private Long patientId;
    private String patientName;
    private Long staffId;
    private String staffName;
    private LocalDateTime visitTime;
    private String chiefComplaint;
    private String diagnosis;
    private Integer status;
}
