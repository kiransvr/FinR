package com.fing.backend;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest
class FlywayStartupValidationTest {

    @Test
    void contextLoadsWithFlywayMigrations() {
        // If the Spring context starts successfully, Flyway migration has run.
    }
}
