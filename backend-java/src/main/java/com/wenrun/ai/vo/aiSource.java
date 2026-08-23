package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Python RAG 返回的一条资料来源，供前端展示引用信息。
 */
@NoArgsConstructor
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class aiSource {

    private String id;

    @JsonAlias({"document_id", "documentId"})
    private String documentId;

    private String title;
    private Integer page;
}
