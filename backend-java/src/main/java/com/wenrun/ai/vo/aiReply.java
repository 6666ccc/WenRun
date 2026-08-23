package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@NoArgsConstructor
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class aiReply {
    @JsonAlias("aiReply")
    private String reply;
    private String status;
    private String conversationId;
    private List<String> selectedAgents = new ArrayList<>();
    private List<aiSource> sources = new ArrayList<>();
}
