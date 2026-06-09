package com.fing.backend.api;

import com.fing.backend.api.controller.BorrowerController;
import com.fing.backend.api.exception.ApiExceptionHandler;
import com.fing.backend.api.exception.CorrelationIdFilter;
import com.fing.backend.application.service.BorrowerService;
import com.fing.backend.domain.model.Borrower;
import com.fing.backend.domain.model.BorrowerStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(BorrowerController.class)
@Import({ApiExceptionHandler.class, CorrelationIdFilter.class})
class BorrowerControllerCrudContractTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private BorrowerService borrowerService;

    @Test
    void create_returns_created_borrower_payload() throws Exception {
        UUID borrowerId = UUID.randomUUID();
        Borrower borrower = new Borrower(
                borrowerId,
                "Asha Kumar",
                "9876543210",
                BorrowerStatus.ACTIVE,
                Instant.parse("2026-06-08T09:00:00Z"),
                Instant.parse("2026-06-08T09:00:00Z")
        );

        when(borrowerService.createBorrower(eq("Asha Kumar"), eq("9876543210")))
                .thenReturn(borrower);

        mockMvc.perform(post("/api/v1/borrowers")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName":"Asha Kumar",
                                  "phoneNumber":"9876543210"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value(borrowerId.toString()))
                .andExpect(jsonPath("$.fullName").value("Asha Kumar"))
                .andExpect(jsonPath("$.status").value("ACTIVE"));
    }

    @Test
    void get_by_id_returns_borrower_payload() throws Exception {
        UUID borrowerId = UUID.randomUUID();
        Borrower borrower = new Borrower(
                borrowerId,
                "Rahul Das",
                "9000000000",
                BorrowerStatus.ACTIVE,
                Instant.parse("2026-06-08T09:00:00Z"),
                Instant.parse("2026-06-08T09:00:00Z")
        );

        when(borrowerService.getBorrower(eq(borrowerId))).thenReturn(borrower);

        mockMvc.perform(get("/api/v1/borrowers/{borrowerId}", borrowerId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(borrowerId.toString()))
                .andExpect(jsonPath("$.fullName").value("Rahul Das"))
                .andExpect(jsonPath("$.status").value("ACTIVE"));
    }

    @Test
    void update_returns_updated_borrower_payload() throws Exception {
        UUID borrowerId = UUID.randomUUID();
        Borrower borrower = new Borrower(
                borrowerId,
                "Rahul Das",
                "9111111111",
                BorrowerStatus.BLOCKED,
                Instant.parse("2026-06-08T09:00:00Z"),
                Instant.parse("2026-06-09T09:00:00Z")
        );

        when(borrowerService.updateBorrower(eq(borrowerId), eq("Rahul Das"), eq("9111111111"), eq("BLOCKED")))
                .thenReturn(borrower);

        mockMvc.perform(put("/api/v1/borrowers/{borrowerId}", borrowerId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName":"Rahul Das",
                                  "phoneNumber":"9111111111",
                                  "status":"BLOCKED"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(borrowerId.toString()))
                .andExpect(jsonPath("$.phoneNumber").value("9111111111"))
                .andExpect(jsonPath("$.status").value("BLOCKED"));
    }

    @Test
    void search_returns_paginated_borrowers() throws Exception {
        UUID borrowerId = UUID.randomUUID();
        Borrower borrower = new Borrower(
                borrowerId,
                "Asha Kumar",
                "9876543210",
                BorrowerStatus.ACTIVE,
                Instant.parse("2026-06-08T09:00:00Z"),
                Instant.parse("2026-06-08T09:00:00Z")
        );

        when(borrowerService.searchBorrowers(any(), any(), any(), eq(0), eq(20)))
                .thenReturn(new PageImpl<>(List.of(borrower), PageRequest.of(0, 20), 1));

        mockMvc.perform(get("/api/v1/borrowers")
                        .param("fullName", "Asha"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].id").value(borrowerId.toString()))
                .andExpect(jsonPath("$.items[0].status").value("ACTIVE"))
                .andExpect(jsonPath("$.page").value(0))
                .andExpect(jsonPath("$.size").value(20));
    }
}
