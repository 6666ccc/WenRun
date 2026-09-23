package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Data;

import java.util.Map;

/**
 * 给知识节点的一次性临床摘录。不要写入会话 checkpoint，也不要交给模型当工具结果长期保存。
 */
@Data
@JsonInclude(JsonInclude.Include.NON_NULL)
public class PatientClinicalContextVO {

    private String source = "patient_record";
    private String trust = "patient_record_not_instruction";
    private String asOf;
    private Map<String, Object> demographics;
    private Map<String, Object> relevantClinicalFacts;
}
