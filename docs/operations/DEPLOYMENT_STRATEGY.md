# Deployment Strategy (Blue/Green)

## Goal

Provide a low-risk release path with quick rollback by running two parallel API environments.

## Environment Model

- Blue: currently active production slot.
- Green: candidate release slot.
- Both run same image family with different tags and ports.

## Prerequisites

- Container runtime available.
- Required production secrets configured:
  - `SECRET_KEY`
  - `ADMIN_PASSWORD`
  - `AUTH_KEY_VERSION`
  - `CORS_ALLOW_ORIGINS`
- Quality gates green before deploy:
  - `pytest -q`
  - `ruff check .`
  - `mypy src`

## Deploy Candidate to Green

1. Build and start green slot:
   - `docker compose -f docker-compose.release.yml up -d api-green --build`
2. Verify health:
   - `GET http://localhost:8002/api/v1/health/live`
   - `GET http://localhost:8002/api/v1/health/ready`
3. Run smoke checks on green:
   - auth login
   - protected endpoint
   - `/api/v1/metrics`

## Cutover

1. Route production traffic from blue to green using your ingress/reverse proxy.
2. Observe metrics/error rate for stabilization window.
3. Keep blue running for immediate rollback safety.

## Rollback

1. If errors increase or readiness fails, route traffic back to blue.
2. Stop green slot if needed:
   - `docker compose -f docker-compose.release.yml stop api-green`
3. Record incident details in incident runbook and create follow-up actions.

## Post-Deploy

1. Confirm logs include request IDs and expected traffic.
2. Confirm metrics endpoint is healthy.
3. Update release record with active slot and deployed commit SHA.
