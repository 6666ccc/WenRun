package com.wenrun.ai.vo;

import jakarta.validation.constraints.*;
import lombok.Data;
import java.util.List;
import java.util.Map;

@Data
public class AiSummaryCommitRequest {
    @NotBlank @Size(max = 64) private String conversationId;
    @NotBlank @Size(max = 64) private String executionId;
    @NotNull @Min(0) private Long expectedVersion;
    @NotEmpty @Size(max = 200) private List<Long> coveredMessageIds;
    @NotNull private Map<String, Object> summary;
}
