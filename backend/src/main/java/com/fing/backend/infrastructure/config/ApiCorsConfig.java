package com.fing.backend.infrastructure.config;

import com.fing.backend.api.exception.CorrelationIdFilter;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;

@Configuration
public class ApiCorsConfig implements WebMvcConfigurer {

    private final String[] allowedOrigins;

    public ApiCorsConfig(
            @Value("${app.security.cors.allowed-origins:http://localhost:3000,http://127.0.0.1:3000}")
            String allowedOriginsValue
    ) {
        this.allowedOrigins = Arrays.stream(allowedOriginsValue.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isBlank())
                .toArray(String[]::new);
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(allowedOrigins)
                .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                .allowedHeaders("Authorization", "Content-Type", CorrelationIdFilter.CORRELATION_ID_HEADER)
                .exposedHeaders(CorrelationIdFilter.CORRELATION_ID_HEADER);
    }
}
