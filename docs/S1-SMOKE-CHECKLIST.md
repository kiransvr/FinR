# Sprint 1 Smoke Checklist

This checklist is the minimum validation pack for Sprint 1 deliverables.

## Backend Smoke

1. Start PostgreSQL:

```bash
docker compose -f db/docker-compose.yml up -d
```

2. Run backend tests:

```bash
cd backend
mvn test
```

3. Run backend app:

```bash
cd backend
mvn spring-boot:run
```

4. Verify endpoints:
- `GET /api/v1/health` returns HTTP 200 with `status=UP`.
- `GET /actuator/health` returns HTTP 200.
- Invalid borrower payload returns standardized validation error contract.

## Web Smoke

1. Run frontend tests:

```bash
cd frontend
npm test
```

2. Run frontend dev shell:

```bash
cd frontend
npm run dev
```

3. Verify user flow:
- Home shell renders with module navigation.
- Protected route shows auth placeholder when signed out.
- Sign-in placeholder enables route access.

## Mobile Smoke

1. Install dependencies:

```bash
cd mobile
flutter pub get
```

2. Run tests:

```bash
cd mobile
flutter test
```

3. Run app:

```bash
cd mobile
flutter run
```

4. Verify user flow:
- App launches to shell screen.
- Sign-in placeholder route opens.
- Auth service flips session state after sign in.

## Exit Criteria

- No smoke failures in backend/web/mobile sections.
- Any failure is logged using the defect triage template.
