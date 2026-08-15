package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class ChatResponseVO {

    private String reply;
    private String status;
    private String conversationId;
    private String intent;
    private List<Map<String, Object>> interrupts;
}
