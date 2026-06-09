package com.fing.backend.api;

import com.fing.backend.api.controller.HealthController;
import com.fing.backend.api.controller.BorrowerController;
import com.fing.backend.application.service.BorrowerService;
import com.fing.backend.infrastructure.config.ApiCorsConfig;
import com.fing.backend.infrastructure.config.ApiSecurityHeadersFilter;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

@WebMvcTest({HealthController.class, BorrowerController.class})
@Import({ApiSecurityHeadersFilter.class, ApiCorsConfig.class})
class ApiSecurityHeadersContractTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private BorrowerService borrowerService;

    @Test
    void health_response_contains_security_headers() throws Exception {
        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-Content-Type-Options", "nosniff"))
                .andExpect(header().string("X-Frame-Options", "DENY"))
                .andExpect(header().string("Referrer-Policy", "no-referrer"))
                .andExpect(header().string("X-XSS-Protection", "0"));
    }

    @Test
    void cors_preflight_allows_known_local_origin() throws Exception {
        mockMvc.perform(options("/api/v1/health")
                        .header("Origin", "http://localhost:3000")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:3000"));
    }

    @Test
    void borrower_search_response_contains_security_headers() throws Exception {
        when(borrowerService.searchBorrowers(any(), any(), any(), eq(0), eq(20)))
                .thenReturn(new PageImpl<>(List.of(), PageRequest.of(0, 20), 0));

        mockMvc.perform(get("/api/v1/borrowers"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-Content-Type-Options", "nosniff"))
                .andExpect(header().string("X-Frame-Options", "DENY"))
                .andExpect(header().string("Referrer-Policy", "no-referrer"))
                .andExpect(header().string("X-XSS-Protection", "0"));
    }

    @Test
    void borrower_preflight_allows_known_local_origin() throws Exception {
        mockMvc.perform(options("/api/v1/borrowers")
                        .header("Origin", "http://localhost:3000")
                        .header("Access-Control-Request-Method", "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:3000"));
    }
}
