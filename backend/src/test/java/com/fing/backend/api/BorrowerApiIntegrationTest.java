package com.fing.backend.api;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@EnabledIfEnvironmentVariable(named = "DB_URL", matches = ".+")
class BorrowerApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanBorrowers() {
        jdbcTemplate.execute("TRUNCATE TABLE borrowers");
    }

    @Test
    void create_update_get_search_flow_works_against_postgresql() throws Exception {
        MvcResult created = mockMvc.perform(post("/api/v1/borrowers")
                        .contentType("application/json")
                        .content("""
                                {
                                  "fullName":"Asha Kumar",
                                  "phoneNumber":"9876543210"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").isNotEmpty())
                .andExpect(jsonPath("$.status").value("ACTIVE"))
                .andReturn();

        String payload = created.getResponse().getContentAsString();
        String borrowerId = extractJsonString(payload, "id");

        mockMvc.perform(put("/api/v1/borrowers/{borrowerId}", borrowerId)
                        .contentType("application/json")
                        .content("""
                                {
                                  "fullName":"Asha Kumar",
                                  "phoneNumber":"9111111111",
                                  "status":"BLOCKED"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(borrowerId))
                .andExpect(jsonPath("$.phoneNumber").value("9111111111"))
                .andExpect(jsonPath("$.status").value("BLOCKED"));

        mockMvc.perform(get("/api/v1/borrowers/{borrowerId}", borrowerId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(borrowerId))
                .andExpect(jsonPath("$.fullName").value("Asha Kumar"))
                .andExpect(jsonPath("$.status").value("BLOCKED"));

        mockMvc.perform(get("/api/v1/borrowers")
                        .param("fullName", "Asha")
                        .param("page", "0")
                        .param("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].id").value(borrowerId))
                .andExpect(jsonPath("$.items[0].phoneNumber").value("9111111111"))
                .andExpect(jsonPath("$.items[0].status").value("BLOCKED"));
    }

    private String extractJsonString(String json, String field) {
        String token = "\"" + field + "\":\"";
        int start = json.indexOf(token);
        if (start < 0) {
            throw new IllegalStateException("Field not found in payload: " + field);
        }
        int valueStart = start + token.length();
        int valueEnd = json.indexOf('"', valueStart);
        if (valueEnd < 0) {
            throw new IllegalStateException("Invalid payload for field: " + field);
        }
        return json.substring(valueStart, valueEnd);
    }
}
