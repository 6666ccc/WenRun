package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class ChatStreamEventVO {

    private String type;
    private String content;
    private String reply;
    private String conversationId;
    private String intent;
    private String code;
    private String message;
    private String status;
    private List<ChatCitationVO> sources;
    private ChatInterruptVO interrupt;
}
