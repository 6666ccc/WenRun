package com.wenrun.ai.delegation;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Data
@Validated
@ConfigurationProperties(prefix = "ai.delegation")
public class AiDelegationProperties {

    @NotBlank
    private String secret;

    private int expirySeconds = 300;
}
