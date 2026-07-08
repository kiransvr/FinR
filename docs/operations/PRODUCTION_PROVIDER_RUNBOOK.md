# Production Provider Runbook

## Scope

Production deployment plan for this project using:

- Vercel for the public web site
- Render for the FastAPI API
- Neon for PostgreSQL-backed outputs and feedback storage
- Cloudflare optional for DNS and TLS in front of public domains

## Recommended Topology

There are two different web surfaces in this workspace:

1. Static marketing/demo site in [site](C:/loan-default-risk/FinR-clean/site)
2. Streamlit operations dashboard at [app.py](C:/loan-default-risk/FinR-clean/app.py)

Recommended production hosting:

- Vercel: static marketing/demo site
- Render service 1: FastAPI API from [run_api.py](C:/loan-default-risk/FinR-clean/run_api.py)
- Render service 2: Streamlit dashboard from [app.py](C:/loan-default-risk/FinR-clean/app.py)
- Neon: database for SQL-backed output store via `DB_OUTPUT_DATABASE_URL`

Reasoning:

- Vercel is a strong fit for static assets.
- Render is a strong fit for long-running Python services.
- Streamlit is not a natural Vercel workload.

## Canonical App Folder

The active backend/dashboard project folder is [FinR-clean](C:/loan-default-risk/FinR-clean).

Use that folder for:

- API deployment
- Streamlit dashboard deployment
- Render blueprint
- production env configuration

## Neon Setup

1. Create a production database in Neon.
2. Create an application user with a dedicated password.
3. Copy the pooled or direct connection string with SSL enabled.
4. Set `DB_OUTPUT_DATABASE_URL` in Render.
5. Set `OUTPUT_STORE_ADAPTER=db` in Render.

Expected connection string shape:

```text
postgresql+psycopg2://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

## Render API Service

Source:

- Root directory: [FinR-clean](C:/loan-default-risk/FinR-clean)
- Docker image: [Dockerfile](C:/loan-default-risk/FinR-clean/Dockerfile)
- Blueprint: [render.yaml](C:/loan-default-risk/FinR-clean/render.yaml)
- Env template: [FinR-clean/.env.production.example](C:/loan-default-risk/FinR-clean/.env.production.example)

Health checks:

- `/api/v1/health/live`
- `/api/v1/health/ready`

Required env vars:

- `APP_ENV=production`
- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `AUTH_KEY_VERSION`
- `CORS_ALLOW_ORIGINS`
- `OUTPUT_STORE_ADAPTER=db`
- `DB_OUTPUT_DATABASE_URL`
- `ENABLE_DEMO_OFFICER_USER=false`

Recommended operational env vars:

- `JOB_MAX_ATTEMPTS=3`
- `JOB_RETRY_BACKOFF_SECONDS=0.2`
- `JOB_TIMEOUT_SECONDS=60`
- `JOB_RUNNING_STALE_SECONDS=300`
- `JOB_MAX_QUEUED_JOBS=500`

## Render Dashboard Service

Source:

- Root directory: [FinR-clean](C:/loan-default-risk/FinR-clean)
- App entry: [app.py](C:/loan-default-risk/FinR-clean/app.py)
- Blueprint: [render.yaml](C:/loan-default-risk/FinR-clean/render.yaml)

Start command:

```text
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Notes:

- Keep dashboard on Render, not Vercel.
- Use same Neon database env if dashboard reads DB-backed outputs.

## Vercel Web Site

Recommended Vercel deploy target is the static web site at workspace root.

Files:

- [site/index.html](C:/loan-default-risk/FinR-clean/site/index.html)
- [site/styles.css](C:/loan-default-risk/FinR-clean/site/styles.css)
- [site/script.js](C:/loan-default-risk/FinR-clean/site/script.js)
- [site/vercel.json](C:/loan-default-risk/FinR-clean/site/vercel.json)

Current state:

- This site is largely static and not yet wired to the FastAPI backend.
- It can be deployed first as a public marketing/demo site.
- If later needed, add API base URL wiring for live API calls.

## Cloudflare

Optional but recommended for:

- custom DNS
- TLS termination
- WAF/rate limiting

Suggested records:

- `app.yourdomain.com` -> Vercel project
- `api.yourdomain.com` -> Render API service
- `ops.yourdomain.com` -> Render Streamlit dashboard

## CORS

Set `CORS_ALLOW_ORIGINS` on Render API to include only trusted origins, for example:

```text
https://app.yourdomain.com,https://ops.yourdomain.com
```

Do not use wildcard origins in production.

## First Production Release Sequence

1. Deploy Neon database and capture connection string.
2. Deploy Render API service.
3. Verify:
   - `/api/v1/health/live`
   - `/api/v1/health/ready`
   - login
   - one protected endpoint
   - `/api/v1/metrics`
4. Run the pipeline once in production.
5. Confirm model and outputs are generated.
6. Deploy Streamlit dashboard on Render.
7. Deploy static site to Vercel.
8. Configure Cloudflare DNS if using custom domains.

## Go-Live Checks

- `GET /api/v1/health/live` returns 200
- `GET /api/v1/health/ready` returns 200
- admin login works
- at least one protected endpoint works
- pipeline run succeeds
- outputs exist
- metrics endpoint works
- request IDs appear in logs

## Known Constraint

The API root path `/` returns 404 by design. This is not a production issue.
Use `/docs`, `/api/v1/health/live`, or `/api/v1/health/ready` for service checks.
