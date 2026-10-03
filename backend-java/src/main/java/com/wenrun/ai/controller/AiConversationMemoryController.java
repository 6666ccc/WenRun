package com.wenrun.ai.controller;

import com.wenrun.ai.security.DelegatedToolContext;
import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.ai.service.AiConversationMemoryService;
import com.wenrun.ai.vo.AiSummaryCommitRequest;
import com.wenrun.common.Result;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@Validated
@RequiredArgsConstructor
@RequestMapping("/api/internal/ai-tools/conversation-memory")
public class AiConversationMemoryController {
    private final AiConversationMemoryService service;
    private DelegatedToolPrincipal principal(String scope) {
        DelegatedToolPrincipal principal = DelegatedToolContext.getRequired();
        if (!principal.hasScope(scope)) throw new BusinessException(ResultCode.FORBIDDEN, "缺少会话恢复权限");
        return principal;
    }
    @GetMapping("/{conversationId}/messages")
    public Result<Map<String, Object>> messages(@PathVariable String conversationId,
            @RequestParam @Min(0) long afterId, @RequestParam @Min(0) long upperId) {
        return Result.success(service.recovery(principal("conversations:read"), conversationId, afterId, upperId));
    }
    @PostMapping("/summary")
    public Result<Map<String, Object>> commit(@Valid @RequestBody AiSummaryCommitRequest body) {
        return Result.success(service.commit(principal("conversations:write"), body));
    }
}
