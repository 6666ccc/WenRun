package com.wenrun.ai.exception;

import com.wenrun.ai.delegation.AiDelegationException;
import com.wenrun.ai.logging.AiLogSanitizer;
import com.wenrun.ai.tools.exception.AiToolException;
import com.wenrun.ai.tools.vo.AiToolErrorVO;
import com.wenrun.common.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@Slf4j
@RestControllerAdvice(assignableTypes = {
        com.wenrun.ai.controller.AiChatController.class,
        com.wenrun.ai.tools.controller.AiToolsInternalController.class,
})
public class AiExceptionHandler {

    @ExceptionHandler(AiServiceException.class)
    public Result<Void> handleAiServiceException(AiServiceException ex) {
        log.warn("AI 服务调用失败: {}", AiLogSanitizer.redact(ex.getMessage()));
        return Result.fail(ex.getCode(), ex.getMessage());
    }

    @ExceptionHandler(AiToolException.class)
    public ResponseEntity<AiToolErrorVO> handleAiToolException(AiToolException ex) {
        log.warn("AI Tool 失败: {} {}", ex.getCode(), AiLogSanitizer.redact(ex.getMessage()));
        return ResponseEntity.status(statusFor(ex.getCode()))
                .body(new AiToolErrorVO(ex.getCode(), ex.getMessage()));
    }

    @ExceptionHandler(AiDelegationException.class)
    public ResponseEntity<AiToolErrorVO> handleAiDelegationException(AiDelegationException ex) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(new AiToolErrorVO("INSUFFICIENT_SCOPE", ex.getMessage()));
    }

    private static HttpStatus statusFor(String code) {
        return switch (code) {
            case "INSUFFICIENT_SCOPE" -> HttpStatus.FORBIDDEN;
            case "SCHEDULE_NOT_FOUND" -> HttpStatus.NOT_FOUND;
            case "SLOT_SOLD_OUT", "DUPLICATE_REGISTRATION",
                    "INTERRUPT_ALREADY_RESOLVED", "INTERRUPT_EXPIRED" -> HttpStatus.CONFLICT;
            case "INTERRUPT_CONVERSATION_MISMATCH" -> HttpStatus.FORBIDDEN;
            default -> HttpStatus.BAD_REQUEST;
        };
    }
}
