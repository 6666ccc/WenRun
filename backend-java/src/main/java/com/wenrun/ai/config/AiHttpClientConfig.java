package com.wenrun.ai.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * AI 服务 HTTP 客户端配置
 */
@Configuration
@EnableConfigurationProperties(AiServiceProperties.class)
public class AiHttpClientConfig {

    @Bean
    public RestClient aiRestClient(AiServiceProperties properties) {
        return buildRestClient(properties, properties.getReadTimeout());
    }

    @Bean
    public RestClient aiStreamRestClient(AiServiceProperties properties) {
        return buildRestClient(properties, properties.getStreamReadTimeout());
    }

    private static RestClient buildRestClient(AiServiceProperties properties, Duration readTimeout) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.getConnectTimeout());
        factory.setReadTimeout(readTimeout);

        RestClient.Builder builder = RestClient.builder()
                .baseUrl(properties.getBaseUrl())
                .requestFactory(factory);
        if (properties.getApiKey() != null && !properties.getApiKey().isBlank()) {
            builder.defaultHeader("X-Api-Key", properties.getApiKey());
        }
        return builder.build();
    }
}
