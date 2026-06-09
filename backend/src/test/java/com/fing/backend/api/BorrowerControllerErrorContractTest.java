package com.fing.backend.api;

import com.fing.backend.api.controller.BorrowerController;
import com.fing.backend.api.exception.ApiExceptionHandler;
import com.fing.backend.api.exception.CorrelationIdFilter;
import com.fing.backend.application.service.BorrowerService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(BorrowerController.class)
@Import({ApiExceptionHandler.class, CorrelationIdFilter.class})
class BorrowerControllerErrorContractTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private BorrowerService borrowerService;

    @Test
    void validation_failures_return_stable_error_contract() throws Exception {
        mockMvc.perform(post("/api/v1/borrowers")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"fullName\":\"\",\"phoneNumber\":\"12\"}")
                        .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "test-correlation-id"))
                .andExpect(status().isBadRequest())
                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "test-correlation-id"))
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.error").value("Bad Request"))
                .andExpect(jsonPath("$.message").value("Validation failed"))
                .andExpect(jsonPath("$.path").value("/api/v1/borrowers"))
                .andExpect(jsonPath("$.correlationId").value("test-correlation-id"))
                .andExpect(jsonPath("$.validationErrors.length()").value(3));
    }

    @Test
    void not_found_errors_return_stable_error_contract() throws Exception {
        UUID borrowerId = UUID.randomUUID();
        when(borrowerService.getBorrower(any(UUID.class)))
                .thenThrow(new IllegalArgumentException("Borrower not found: " + borrowerId));

        mockMvc.perform(get("/api/v1/borrowers/{borrowerId}", borrowerId)
                        .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "lookup-correlation-id"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "lookup-correlation-id"))
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.error").value("Not Found"))
                .andExpect(jsonPath("$.message").value("Borrower not found: " + borrowerId))
                .andExpect(jsonPath("$.path").value("/api/v1/borrowers/" + borrowerId))
                .andExpect(jsonPath("$.correlationId").value("lookup-correlation-id"))
                .andExpect(jsonPath("$.validationErrors.length()").value(0));
    }

    @Test
    void update_not_found_returns_stable_error_contract() throws Exception {
        UUID borrowerId = UUID.randomUUID();
        when(borrowerService.updateBorrower(any(UUID.class), any(String.class), any(String.class), any(String.class)))
                .thenThrow(new IllegalArgumentException("Borrower not found: " + borrowerId));

        mockMvc.perform(put("/api/v1/borrowers/{borrowerId}", borrowerId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "fullName":"Asha Kumar",
                                  "phoneNumber":"9876543210",
                                  "status":"ACTIVE"
                                }
                                """)
                        .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "update-not-found-correlation-id"))
                .andExpect(status().isNotFound())
                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "update-not-found-correlation-id"))
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.error").value("Not Found"))
                .andExpect(jsonPath("$.message").value("Borrower not found: " + borrowerId))
                .andExpect(jsonPath("$.path").value("/api/v1/borrowers/" + borrowerId))
                .andExpect(jsonPath("$.correlationId").value("update-not-found-correlation-id"))
                .andExpect(jsonPath("$.validationErrors.length()").value(0));
    }

        @Test
        void update_validation_failures_return_stable_error_contract() throws Exception {
                UUID borrowerId = UUID.randomUUID();

                mockMvc.perform(put("/api/v1/borrowers/{borrowerId}", borrowerId)
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content("""
                                                                {
                                                                    "fullName":"",
                                                                    "phoneNumber":"12",
                                                                    "status":"UNKNOWN"
                                                                }
                                                                """)
                                                .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "update-correlation-id"))
                                .andExpect(status().isBadRequest())
                                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "update-correlation-id"))
                                .andExpect(jsonPath("$.status").value(400))
                                .andExpect(jsonPath("$.error").value("Bad Request"))
                                .andExpect(jsonPath("$.message").value("Validation failed"))
                                .andExpect(jsonPath("$.path").value("/api/v1/borrowers/" + borrowerId))
                                .andExpect(jsonPath("$.correlationId").value("update-correlation-id"))
                                .andExpect(jsonPath("$.validationErrors.length()").value(4));
        }

        @Test
        void search_query_errors_return_stable_error_contract() throws Exception {
                mockMvc.perform(get("/api/v1/borrowers")
                                                .param("size", "101")
                                                .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-correlation-id"))
                                .andExpect(status().isBadRequest())
                                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-correlation-id"))
                                .andExpect(jsonPath("$.status").value(400))
                                .andExpect(jsonPath("$.error").value("Bad Request"))
                                .andExpect(jsonPath("$.message").value("size must be between 1 and 100"))
                                .andExpect(jsonPath("$.path").value("/api/v1/borrowers"))
                                .andExpect(jsonPath("$.correlationId").value("search-correlation-id"))
                                .andExpect(jsonPath("$.validationErrors.length()").value(0));
        }

        @Test
        void search_invalid_id_returns_stable_error_contract() throws Exception {
                mockMvc.perform(get("/api/v1/borrowers")
                                                .param("id", "invalid-uuid")
                                                .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-invalid-id-correlation-id"))
                                .andExpect(status().isBadRequest())
                                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-invalid-id-correlation-id"))
                                .andExpect(jsonPath("$.status").value(400))
                                .andExpect(jsonPath("$.error").value("Bad Request"))
                                .andExpect(jsonPath("$.message").value("Invalid value for parameter 'id'"))
                                .andExpect(jsonPath("$.path").value("/api/v1/borrowers"))
                                .andExpect(jsonPath("$.correlationId").value("search-invalid-id-correlation-id"))
                                .andExpect(jsonPath("$.validationErrors.length()").value(0));
        }

        @Test
        void create_full_name_too_long_returns_validation_error_contract() throws Exception {
                String overSizedName = "A".repeat(151);

                mockMvc.perform(post("/api/v1/borrowers")
                                                .contentType(MediaType.APPLICATION_JSON)
                                                .content("""
                                                                {
                                                                  "fullName":"%s",
                                                                  "phoneNumber":"9876543210"
                                                                }
                                                                """.formatted(overSizedName))
                                                .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "create-validation-correlation-id"))
                                .andExpect(status().isBadRequest())
                                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "create-validation-correlation-id"))
                                .andExpect(jsonPath("$.status").value(400))
                                .andExpect(jsonPath("$.error").value("Bad Request"))
                                .andExpect(jsonPath("$.message").value("Validation failed"))
                                .andExpect(jsonPath("$.path").value("/api/v1/borrowers"))
                                .andExpect(jsonPath("$.correlationId").value("create-validation-correlation-id"))
                                .andExpect(jsonPath("$.validationErrors.length()").value(1));
        }

        @Test
        void search_phone_number_validation_error_returns_stable_error_contract() throws Exception {
                mockMvc.perform(get("/api/v1/borrowers")
                                                .param("phoneNumber", "12ab")
                                                .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-phone-correlation-id"))
                                .andExpect(status().isBadRequest())
                                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-phone-correlation-id"))
                                .andExpect(jsonPath("$.status").value(400))
                                .andExpect(jsonPath("$.error").value("Bad Request"))
                                .andExpect(jsonPath("$.message").value("phoneNumber must be 10 to 15 digits"))
                                .andExpect(jsonPath("$.path").value("/api/v1/borrowers"))
                                .andExpect(jsonPath("$.correlationId").value("search-phone-correlation-id"))
                                .andExpect(jsonPath("$.validationErrors.length()").value(0));
        }

        @Test
        void search_full_name_too_short_returns_stable_error_contract() throws Exception {
                mockMvc.perform(get("/api/v1/borrowers")
                                                .param("fullName", "A")
                                                .header(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-fullname-correlation-id"))
                                .andExpect(status().isBadRequest())
                                .andExpect(header().string(CorrelationIdFilter.CORRELATION_ID_HEADER, "search-fullname-correlation-id"))
                                .andExpect(jsonPath("$.status").value(400))
                                .andExpect(jsonPath("$.error").value("Bad Request"))
                                .andExpect(jsonPath("$.message").value("fullName must be between 2 and 150 characters"))
                                .andExpect(jsonPath("$.path").value("/api/v1/borrowers"))
                                .andExpect(jsonPath("$.correlationId").value("search-fullname-correlation-id"))
                                .andExpect(jsonPath("$.validationErrors.length()").value(0));
        }
}