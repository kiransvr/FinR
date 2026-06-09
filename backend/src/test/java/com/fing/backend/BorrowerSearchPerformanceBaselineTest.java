package com.fing.backend;

import com.fing.backend.domain.model.Borrower;
import com.fing.backend.domain.port.BorrowerRepository;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.Page;
import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@EnabledIfEnvironmentVariable(named = "DB_URL", matches = ".+")
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class BorrowerSearchPerformanceBaselineTest {

    private static final UUID TARGET_ID = UUID.fromString("00000000-0000-4000-a000-000000424242");
    private static final String TARGET_PHONE = "9000042424";
    private static final String NAME_PREFIX = "Search Baseline";
    private static final Instant BASELINE_INSTANT = Instant.parse("2026-06-09T00:00:00Z");

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private BorrowerRepository borrowerRepository;

    @BeforeAll
    void seedData() {
        jdbcTemplate.execute("TRUNCATE TABLE borrowers");
        jdbcTemplate.update(
                "INSERT INTO borrowers (id, full_name, phone_number, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                TARGET_ID,
                NAME_PREFIX + " Target",
                TARGET_PHONE,
                "ACTIVE",
                Timestamp.from(BASELINE_INSTANT),
                Timestamp.from(BASELINE_INSTANT)
        );
        jdbcTemplate.execute("""
                INSERT INTO borrowers (id, full_name, phone_number, status, created_at, updated_at)
                SELECT (
                    substr(md5('borrower-' || gs::text), 1, 8) || '-' ||
                    substr(md5('borrower-' || gs::text), 9, 4) || '-' ||
                    '4' || substr(md5('borrower-' || gs::text), 14, 3) || '-' ||
                    'a' || substr(md5('borrower-' || gs::text), 18, 3) || '-' ||
                    substr(md5('borrower-' || gs::text), 21, 12)
                )::uuid,
                CASE
                    WHEN gs BETWEEN 50000 AND 50999 THEN 'Search Baseline ' || lpad(gs::text, 6, '0')
                    ELSE 'Borrower ' || lpad(gs::text, 6, '0')
                END,
                (9000000000 + gs)::text,
                'ACTIVE',
                TIMESTAMPTZ '2026-06-09T00:00:00Z',
                TIMESTAMPTZ '2026-06-09T00:00:00Z'
                FROM generate_series(1, 100000) AS gs
                ON CONFLICT (id) DO NOTHING
                """);
        jdbcTemplate.execute("ANALYZE borrowers");
    }

    @Test
    void explain_plans_use_indexes_for_id_phone_and_name_searches() {
        String idPlan = explain("SELECT id FROM borrowers WHERE id = '%s' LIMIT 20".formatted(TARGET_ID));
        String phonePlan = explain("SELECT id FROM borrowers WHERE phone_number = '%s' LIMIT 20".formatted(TARGET_PHONE));
        String namePlan = explain("SELECT id FROM borrowers WHERE lower(full_name) LIKE 'search baseline%%' LIMIT 20");

        assertTrue(idPlan.contains("borrowers_pkey"), idPlan);
        assertTrue(phonePlan.contains("idx_borrowers_phone_number"), phonePlan);
        assertTrue(namePlan.contains("idx_borrowers_full_name_prefix"), namePlan);
    }

    @Test
    void repository_name_search_completes_under_two_seconds_for_baseline_dataset() {
        long startedAt = System.nanoTime();
        Page<Borrower> result = borrowerRepository.search(
                Optional.empty(),
                Optional.empty(),
                Optional.of(NAME_PREFIX),
                0,
                20
        );
        long durationMillis = (System.nanoTime() - startedAt) / 1_000_000;

        assertFalse(result.isEmpty());
        assertTrue(durationMillis < 2000, "Expected search under 2000ms but was %dms".formatted(durationMillis));
    }

    private String explain(String query) {
        List<String> lines = jdbcTemplate.query(
                "EXPLAIN (ANALYZE, BUFFERS) " + query,
                (resultSet, rowNum) -> resultSet.getString(1)
        );
        return String.join("\n", lines);
    }
}
