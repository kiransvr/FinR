# FinG Architecture (MVC 3-Tier)

## Architecture Style

FinG follows an industry-standard MVC implementation over a 3-tier architecture:

1. Presentation Tier
2. Application Tier
3. Data Tier

This keeps UI concerns, business workflows, and persistence concerns separated for maintainability, testability, and scale.

## Tiers

### 1) Presentation Tier

Responsibilities:
- Render UI and collect user input
- Client-side validation and UX flow
- Call backend APIs and display results

Components:
- Web app: Next.js
- Mobile app: Flutter

MVC mapping:
- Views: Screens/pages and widgets/components
- Controllers: Route handlers, view-model/state controllers, and form handlers in the client apps
- Models (presentation): DTO/view models for display and input

### 2) Application Tier

Responsibilities:
- Implement business use cases and rules
- Enforce workflow and authorization checks
- Expose APIs for web/mobile clients
- Publish async tasks/events

Components:
- Backend API: Spring Boot
- Modules: borrower, loan, demand, recovery, notifications, reports

MVC mapping:
- Controllers: REST controllers (request/response boundary)
- Models (domain/application): entities, value objects, use-case DTOs
- Services: orchestration and core business rules

### 3) Data Tier

Responsibilities:
- Durable data storage and retrieval
- Caching and queue-based async processing
- Data integrity and performance optimization

Components:
- PostgreSQL: system of record
- Redis: cache, queues, and short-lived state

MVC mapping:
- Model persistence: repositories/DAOs and ORM mappings

## Logical Layering Inside Backend (Spring Boot)

Recommended package flow:
- api (controllers, request/response DTOs)
- application (use cases, service orchestration)
- domain (business rules, aggregates, value objects)
- infrastructure (repositories, messaging, external adapters)

### Backend Package Conventions and Naming Standard

- `com.fing.backend.api.controller`: REST controllers only
- `com.fing.backend.api.dto`: request and response DTOs only
- `com.fing.backend.api.exception`: API-facing exception translation only
- `com.fing.backend.application.service`: use-case orchestration services only
- `com.fing.backend.domain.model`: domain entities and value objects
- `com.fing.backend.domain.port`: repository and external service contracts owned by domain/application
- `com.fing.backend.infrastructure.persistence`: repository adapters and persistence mapping logic
- `com.fing.backend.infrastructure.persistence.entity`: JPA entities only
- `com.fing.backend.infrastructure.persistence.jpa`: Spring Data repositories only

Naming rules:
- Controllers end with `Controller`
- Application services end with `Service`
- Domain repository contracts end with `Repository`
- Infrastructure adapters use a technology-specific prefix or suffix such as `PostgresBorrowerRepository`
- DTO classes use request/response suffixes such as `CreateBorrowerRequest` and `BorrowerResponse`

Review rules:
- `api` may depend on `application` and DTOs, but not directly on persistence adapters
- `application` may depend on `domain` and domain ports, but not on web concerns
- `domain` must stay framework-agnostic and must not carry Spring stereotypes
- `infrastructure` implements ports and may depend on framework libraries

Dependency rule:
- Outer layers depend on inner abstractions; domain does not depend on frameworks.

## Request Lifecycle

1. User action from Next.js or Flutter UI
2. API controller validates request and authorizes access
3. Application service executes use case
4. Domain model enforces business rules
5. Repository persists/reads from PostgreSQL
6. Optional cache or async event via Redis
7. API returns response DTO to client

## Industry Practices Adopted

- API-first design with versioned REST endpoints (for example: /api/v1/...)
- DTO isolation between API and domain
- Centralized validation and exception handling
- Stateless backend services for horizontal scaling
- Idempotent operations for critical financial updates
- Audit fields and change history for financial traceability
- Observability: structured logging, metrics, health checks, tracing
- Security: OAuth2/JWT, role-based access control, least privilege

## NFR Targets (Initial)

- Availability: 99.9% target for API services
- P95 API latency: < 300 ms for core read operations
- Data durability: daily backup + point-in-time recovery for PostgreSQL
- Security baseline: OWASP ASVS aligned controls for auth/session/input handling

## Suggested Next Steps

1. Define bounded contexts and module contracts in docs/MODULES.md.
2. Create API contracts (OpenAPI) for borrower and loan modules first.
3. Establish backend project structure with layered package template.
4. Add CI checks: test, lint, SAST, dependency vulnerability scan.
