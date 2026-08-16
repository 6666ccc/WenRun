package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.Map;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class ChatInterruptVO {

    private String interruptId;
    private String action;
    private String summary;
    private Map<String, Object> params;
}
