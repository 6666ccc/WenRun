package com.wenrun.ai.controller;

import com.wenrun.ai.service.aiService;
import com.wenrun.ai.vo.aiReply;
import com.wenrun.ai.vo.aiRequest;
import com.wenrun.common.Result;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class aiController {
    private final aiService aiService;

    @PostMapping("/chat/v1")
    public Result<aiReply> chat(@Valid @RequestBody aiRequest request) {
        return Result.success(aiService.chat(request));
    }
}
