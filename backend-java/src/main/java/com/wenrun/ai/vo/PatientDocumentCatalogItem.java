package com.wenrun.ai.vo;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 报告目录项。只有标题、类型和日期，没有文件地址。
 */
@Data
public class PatientDocumentCatalogItem {

    private Long id;
    private String docType;
    private String title;
    private LocalDateTime occurredAt;
}
