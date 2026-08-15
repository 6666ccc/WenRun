package com.wenrun.dto;

import lombok.Data;

@Data
public class VisitUpdateDTO {
    private String chiefComplaint;
    private String diagnosis;
    private Boolean complete;
}
