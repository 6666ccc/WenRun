package com.wenrun.ai.knowledge.model;

import com.wenrun.common.exception.BusinessException;
import lombok.Getter;

import java.util.Arrays;

@Getter
public enum KnowledgeBaseType {

    MEDICAL_GENERAL("medical-general", "wenrun_medical_general"),
    HOSPITAL_CUSTOM("hospital-custom", "wenrun_hospital_custom");

    private final String pathValue;
    private final String collectionName;

    KnowledgeBaseType(String pathValue, String collectionName) {
        this.pathValue = pathValue;
        this.collectionName = collectionName;
    }

    public static KnowledgeBaseType fromPath(String value) {
        return Arrays.stream(values())
                .filter(type -> type.pathValue.equals(value))
                .findFirst()
                .orElseThrow(() -> new BusinessException("不支持的知识库类型: " + value));
    }
}
