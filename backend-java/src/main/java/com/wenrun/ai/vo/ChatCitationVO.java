package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class ChatCitationVO {

    private String id;
    private String kind;
    private String documentId;
    private String title;
    private Integer page;
    private String section;
    private String excerpt;
    private String toolName;
    private String queryTime;
    private String summary;
}
