# FinG Setup (Planning Phase)

## Current State

Planning and architecture definition.

## Planned Runtime Stack

- Frontend Web: Next.js
- Mobile: Flutter
- Backend: Spring Boot
- Database: PostgreSQL
- Cache/Queue: Redis

## Immediate Setup Tasks

1. Initialize backend Spring Boot service skeleton.
2. Initialize frontend Next.js app with API client layer.
3. Initialize Flutter app with auth and collection flow shell.
4. Define local Docker Compose for PostgreSQL and Redis.

## Local Database (PostgreSQL)

Run from repository root:

```bash
docker compose -f db/docker-compose.yml up -d
```

Default local DB settings used by backend:

- DB URL: jdbc:postgresql://localhost:5432/fing
- DB Username: fing
- DB Password: fing

You can override these via environment variables:

- DB_URL
- DB_USERNAME
- DB_PASSWORD

## Backend Run

Run from backend directory:

```bash
mvn spring-boot:run
```

Flyway migration `V1__create_borrowers_table.sql` runs on startup.

## S1-02 Migration Validation

Use this sequence to validate that Flyway runs on Spring Boot startup.

1. Start PostgreSQL:

```bash
docker compose -f db/docker-compose.yml up -d
```

2. If Maven is installed locally, run:

```bash
cd backend
mvn -Dtest=FlywayStartupValidationTest test
```

3. If Maven is not installed locally, run the same test via Dockerized Maven:

```bash
docker run --rm \
	--add-host host.docker.internal:host-gateway \
	-e DB_URL=jdbc:postgresql://host.docker.internal:5432/fing \
	-e DB_USERNAME=fing \
	-e DB_PASSWORD=fing \
	-v ${PWD}/backend:/workspace \
	-w /workspace \
	maven:3.9.9-eclipse-temurin-21 \
	mvn -Dtest=FlywayStartupValidationTest test
```

Alternative one-command execution from repository root:

```bash
powershell -ExecutionPolicy Bypass -File scripts/validate-s1-02.ps1
```

Expected result:
- Spring context starts.
- Flyway applies migration `V1__create_borrowers_table.sql`.
- Test `FlywayStartupValidationTest` passes.

## Backend Profiles

- Default profile: `local`
- Override profile with `SPRING_PROFILES_ACTIVE`

Example:

```bash
SPRING_PROFILES_ACTIVE=local mvn spring-boot:run
```

## S2-03 Search Performance Baseline

Borrower search baseline constraints:

- `id`: exact match using the primary-key index.
- `phoneNumber`: exact match using `idx_borrowers_phone_number`.
- `fullName`: case-insensitive prefix match using `idx_borrowers_full_name_prefix`.
- API paging defaults: `page=0`, `size=20`.
- API paging upper bound: `size=100`.

Baseline verification command:

```bash
cd backend
mvn -Dtest=BorrowerSearchPerformanceBaselineTest test
```

Prerequisites:

- PostgreSQL is running and reachable through `DB_URL`, `DB_USERNAME`, and `DB_PASSWORD`.
- Flyway migrations `V1` through `V3` are applied on startup.

What the baseline test does:

- Seeds a 100,001-row borrower dataset.
- Verifies `EXPLAIN ANALYZE` uses indexed access paths for borrower ID, phone number, and name prefix searches.
- Verifies the first page of name-prefix search returns in under 2 seconds for the baseline dataset.

Expected scaling path:

- Keep exact-match filters on borrower ID and phone number for selective lookups.
- Keep name search as a prefix match for the indexed baseline.
- If product needs infix search or materially larger datasets, move to a trigram/GIN strategy or a dedicated search service.

## S2-06 Borrower API Contract and Integration Test Pack

Test pack scope:

- Contract tests: success and error contracts for create, update, get, and search endpoints.
- Integration test: create-update-get-search flow against PostgreSQL.

Run locally with PostgreSQL:

```bash
docker compose -f db/docker-compose.yml up -d
cd backend
mvn -Dtest=BorrowerControllerCrudContractTest,BorrowerControllerErrorContractTest,BorrowerApiIntegrationTest test
```

CI execution:

- Workflow: `.github/workflows/backend-ci.yml`
- Job: `borrower-api-test-pack`
- Trigger: pull requests and pushes to `main`

Evidence collection for sprint review:

- Download artifact: `borrower-api-test-pack-reports` from the CI run.
- Review surefire reports for:
	- `TEST-com.fing.backend.api.BorrowerControllerCrudContractTest.xml`
	- `TEST-com.fing.backend.api.BorrowerControllerErrorContractTest.xml`
	- `TEST-com.fing.backend.api.BorrowerApiIntegrationTest.xml`

## S2-07 Observability and Audit Enrichment

Borrower operation logs now emit structured key-value records with operation outcome and correlation context:

- Search success log:
	- `event=borrower_query operation=search outcome=success correlationId=<id> ...`
- Mutation success logs:
	- `event=borrower_mutation operation=create outcome=success correlationId=<id> actor=<actor> source=<source> ...`
	- `event=borrower_mutation operation=update outcome=success correlationId=<id> actor=<actor> source=<source> ...`
- API error log:
	- `event=api_error outcome=failure correlationId=<id> status=<status> path=<path> ...`

Correlation and audit placeholder headers:

- Correlation: `X-Correlation-Id`
- Actor placeholder: `X-Actor-Id` (defaults to `anonymous-placeholder`)
- Source placeholder: `X-Source-System` (defaults to `api`)

Actuator endpoints (remain available):

- `GET /actuator/health`
- `GET /actuator/info`

Metrics notes:

- Track borrower operation latency from `elapsedMs` fields in structured logs.
- Use correlation IDs to stitch borrower API request traces across success and failure events.
