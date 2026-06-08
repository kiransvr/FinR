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
