package com.wenrun.ai.tools.exception;

import lombok.Getter;

@Getter
public class AiToolException extends RuntimeException {

    private final String code;

    public AiToolException(String code, String message) {
        super(message);
        this.code = code;
    }
}
