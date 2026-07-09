# Deploying to Render (Production Guide)

## Overview
This document provides step-by-step instructions to deploy the **Loan Default Risk API** and **Dashboard** to [Render.com](https://render.com), a managed container & serverless platform.

## Prerequisites
- Render account (sign up at [https://render.com](https://render.com) using GitHub)
- `kiransvr/FinR` repository access
- Generated strong secrets for production

## Architecture
Two separate services work together:
- **API** (Docker): FastAPI backend on port 8001 with durable job queue and Postgres output store
- **Dashboard** (Python): Streamlit UI communicating with the API

Both read `render.yaml` in the repository root for configuration.

## Step-by-Step Deployment

### 1. Prepare Secrets
Generate production-safe values:

```bash
# Secret key (JWT signing) — 32+ random chars
openssl rand -base64 32

# Example output:
# qR/7g5K+mP2L8n9Q1X5vZ3bF6dH9jK2L+mP5sT8uX=
```

Have ready:
- `SECRET_KEY`: Output from above
- `ADMIN_PASSWORD`: Strong admin password
- `AUTH_KEY_VERSION`: Start with `v1`
- `DB_OUTPUT_DATABASE_URL`: PostgreSQL connection string (or local SQLite during testing)

### 2. Connect GitHub
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New +** → **Web Service**
3. Select **Public GitHub repository**
4. Search for `kiransvr/FinR`
5. Click **Connect**

Render will detect `render.yaml` and show 2 services ready for configuration.

### 3. Configure & Deploy API Service

**Service Details:**
- **Name:** `loan-default-risk-api` (from `render.yaml`)
- **Runtime:** Docker
- **Plan:** Starter (free tier, or Starter Pro for production SLAs)
- **Region:** US East (default) or choose closest to you

**Environment Variables** (set in Render dashboard):

| Key | Value | Notes |
|---|---|---|
| `SECRET_KEY` | (your 32+ char secret) | Must be set; cannot be empty in prod |
| `ADMIN_PASSWORD` | (your strong password) | For demo auth |
| `AUTH_KEY_VERSION` | `v1` | Increment to invalidate all tokens |
| `CORS_ALLOW_ORIGINS` | `https://loan-default-risk-dashboard-XXXX.onrender.com` | Set after dashboard deploys |
| `DB_OUTPUT_DATABASE_URL` | (PostgreSQL URL or file path) | Optional; defaults to SQLite |

**Deploy:**
1. Click **Create Web Service**
2. Render builds the Docker image and deploys
3. Wait ~3–5 minutes for the service to start
4. Once deployed, copy the **service URL**: `https://loan-default-risk-api-XXXXX.onrender.com`

**Verify:**
```bash
curl https://loan-default-risk-api-XXXXX.onrender.com/api/v1/health/live
# Expected response: {"status":"ok","model_loaded":false,"pipeline_outputs_available":false}
```

### 4. Configure & Deploy Dashboard Service

**Service Details:**
- **Name:** `loan-default-risk-dashboard`
- **Runtime:** Python (3.12)
- **Plan:** Starter
- **Region:** Same as API for latency

**Environment Variables:**

| Key | Value | Notes |
|---|---|---|
| `SECRET_KEY` | (same as API) | Must match API |
| `ADMIN_PASSWORD` | (same as API) | Must match API |
| `AUTH_KEY_VERSION` | (same as API) | Must match API |
| `CORS_ALLOW_ORIGINS` | `https://loan-default-risk-dashboard-XXXXX.onrender.com` | **Set after this service deploys** |
| `DB_OUTPUT_DATABASE_URL` | (same as API) | Must match API |
| `APP_ENV` | `production` | Already set in `render.yaml` |

**Important:** The Streamlit service needs to communicate with the API. Ensure both services:
1. Are on the same `DB_OUTPUT_DATABASE_URL` (shared output store)
2. Have matching auth credentials (`SECRET_KEY`, `ADMIN_PASSWORD`)

**Deploy:**
1. Click **Create Web Service**
2. Render installs Python 3.12 and dependencies
3. Starts Streamlit server on the assigned port
4. Wait ~2–3 minutes
5. Copy the **service URL**: `https://loan-default-risk-dashboard-XXXX.onrender.com`

### 5. Update CORS After Both Deploy

Once both services have public URLs:

1. Return to **API service** settings in Render
2. Update `CORS_ALLOW_ORIGINS` to: `https://loan-default-risk-dashboard-XXXX.onrender.com`
3. Click **Save**

This allows the dashboard (running on a different domain) to call the API without CORS errors.

## Verify Complete Deployment

### 1. Health Checks
```bash
# API liveness
curl https://loan-default-risk-api-XXXX.onrender.com/api/v1/health/live

# API readiness
curl https://loan-default-risk-api-XXXX.onrender.com/api/v1/health/ready

# Dashboard (should show login page)
curl https://loan-default-risk-dashboard-XXXX.onrender.com -I
# Look for: 200 OK
```

### 2. Login to Dashboard
1. Open `https://loan-default-risk-dashboard-XXXX.onrender.com`
2. Log in with credentials: `admin` / `<ADMIN_PASSWORD>`
3. You should see the Risk Dashboard

### 3. Run a Test Pipeline
1. In the sidebar, click **Upload loan data**
2. Select the sample CSV from `data/raw/Loan Accounts-Dummy.csv`
3. Click **Run scoring**
4. Wait for pipeline to complete
5. Verify outputs appear in dashboard tabs

## Production Hardening Checklist

- [ ] `SECRET_KEY` is strong and unique (32+ random chars, not default)
- [ ] `ADMIN_PASSWORD` is strong and unique
- [ ] `CORS_ALLOW_ORIGINS` points only to your dashboard URL
- [ ] Database backup strategy in place (if using PostgreSQL)
- [ ] Logs are monitored (Render provides built-in log viewer)
- [ ] Uptime monitoring configured (external service or Render alerts)
- [ ] Custom domain configured (optional, in Render settings)
- [ ] Rate limits appropriate for your user base

## Scaling & Monitoring

### Monitor Logs
1. In Render dashboard, open the **API** or **Dashboard** service
2. Click **Logs** tab
3. Review recent entries for errors or warnings

### Manual Redeploy
1. Go to service → **Deploys** tab
2. Select a previous deployment or current → **Redeploy**

### Free Tier Limitations
- Services spin down after 15 min of inactivity (cold start ~30s)
- Starter plans have resource limits
- For production SLAs, upgrade to **Starter Pro** or higher

## Troubleshooting

### Dashboard Fails to Render
**Symptom:** "API unreachable" or blank page  
**Fix:**
1. Verify API service is running: check **Logs**
2. Verify `CORS_ALLOW_ORIGINS` in API includes dashboard URL
3. Check dashboard logs for connection errors
4. Ensure both services share the same `DB_OUTPUT_DATABASE_URL`

### Pipeline Timeouts
**Symptom:** "Pipeline failed" after upload  
**Fix:**
1. Check API logs for timeout or out-of-memory errors
2. Consider upgrading to Starter Pro for more CPU/RAM
3. Increase `JOB_TIMEOUT_SECONDS` in API env vars (default 60s)

### Health Check Fails
**Symptom:** "Build succeeded but service won't start"  
**Fix:**
1. Check API logs: look for `SECRET_KEY missing` or similar
2. Verify all required secrets are set
3. Check Docker image built correctly
4. Restart service: go to **Settings** → **Restart**

## Updating to a New Release

1. Push fixes to `origin/main` branch
2. If `autoDeploy` enabled (default for API), Render auto-redeploys
3. For manual services, click **Redeploy** in the Renders dashboard
4. Verify health endpoints after deploy

## Support & Further Reading

- [Render Documentation](https://render.com/docs)
- [Render Python Deployment Guide](https://render.com/docs/deploy-python)
- [Render Docker Deployment Guide](https://render.com/docs/docker)
- Project repo: [kiransvr/FinR](https://github.com/kiransvr/FinR)
