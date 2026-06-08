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

## Backend Profiles

- Default profile: `local`
- Override profile with `SPRING_PROFILES_ACTIVE`

Example:

```bash
SPRING_PROFILES_ACTIVE=local mvn spring-boot:run
```
