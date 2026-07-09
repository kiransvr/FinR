# FinR Production Deployment — Ready for Render ✅

## Current Status
- **Code:** All 230 tests passing, linting clean, type-checked
- **Configuration:** `render.yaml` fixed and committed (3 commits since last deploy)
- **Repository:** Latest commit pushed to `origin/main`
- **URL Structure:** Both services configured with auto-health checks
- **Next Step:** Connect GitHub to Render account and trigger deployment

## What's Deployed (in render.yaml)

### 1. API Service (`loan-default-risk-api`)
- **Language/Runtime:** Python 3.12 in Docker
- **Port:** 8001
- **Entry Point:** `python run_api.py --host 0.0.0.0 --port 8001`
- **Health Check:** `GET /api/v1/health/live` (every 30 sec, 5 sec timeout, 20 sec start period)
- **Features:**
  - JWT auth with bearer tokens
  - Risk scoring via ML model (scikit-learn Logistic Regression)
  - Background job queue (SQLite persistence)
  - Rate limiting (10 req/sec by default)
  - CORS enabled for dashboard
  - Durable output store (CSV or PostgreSQL)

### 2. Dashboard Service (`loan-default-risk-dashboard`)
- **Language/Runtime:** Python 3.12 (Streamlit)
- **Port:** 8501 (default Streamlit)
- **Entry Point:** `streamlit run app.py --server.port 8501 --server.headless true`
- **Features:**
  - Interactive UI for uploading loan files
  - Risk filtering and intelligence tables
  - Officer KPIs and visit planning
  - Field feedback collection
  - Admin controls for gate profiles and rollout management

## Deployment Workflow

### First Time Setup (Once)
```
1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service" → "Public GitHub repository"
3. Search for kiransvr/FinR → Click "Connect"
4. Render sees render.yaml and shows both services
5. Set environment variables for each service:
   - SECRET_KEY (required, 32+ random chars)
   - ADMIN_PASSWORD (required, strong password)
   - CORS_ALLOW_ORIGINS (set to dashboard URL after it deploys)
6. Deploy API first (auto-deploy enabled)
7. Deploy Dashboard second (manual)
8. Update CORS_ALLOW_ORIGINS in API after dashboard has a URL
```

### Result
After ~5 minutes, you'll have:
- **API:** `https://loan-default-risk-api-XXXXX.onrender.com`
- **Dashboard:** `https://loan-default-risk-dashboard-XXXXX.onrender.com`

## Quick Environment Setup

**For Render Dashboard Settings:**

```env
# API Service Environment Variables
SECRET_KEY=<generate with: openssl rand -base64 32>
ADMIN_PASSWORD=<strong-password>
AUTH_KEY_VERSION=v1
CORS_ALLOW_ORIGINS=https://loan-default-risk-dashboard-XXXXX.onrender.com
DB_OUTPUT_DATABASE_URL=sqlite:/tmp/output_store.db
APP_ENV=production
OUTPUT_STORE_ADAPTER=db
ENABLE_DEMO_OFFICER_USER=false
JOB_MAX_ATTEMPTS=3

# Dashboard Service Environment Variables
(Same as API service above)
```

## Post-Deployment Verification

```bash
# 1. Health check
curl https://loan-default-risk-api-XXXXX.onrender.com/api/v1/health/live
# Expected: {"status":"ok","..."}

# 2. API docs
curl https://loan-default-risk-api-XXXXX.onrender.com/docs
# Expected: Swagger UI page

# 3. Login to dashboard
# Visit: https://loan-default-risk-dashboard-XXXXX.onrender.com
# Use: admin / <ADMIN_PASSWORD>
```

## Key Files
- `render.yaml` — Render configuration (2 services defined)
- `Dockerfile` — API Docker image definition
- `app.py` — Streamlit dashboard entry point
- `run_api.py` — FastAPI startup script
- `src/` — Application code (business logic, API, auth, job queue)
- `docs/operations/RENDER_DEPLOYMENT_GUIDE.md` — Full deployment instructions

## Latest Commits
```
916ecd9  Docs: add comprehensive Render deployment guide
56736f7  Fix render.yaml: remove wrong rootDir, add pythonVersion 3.12 to dashboard service
6083e7f  Fix: return 401 (not 403) for missing bearer token; replace deprecated pd.Timestamp.utcnow()
```

## Known Limits (Free Tier)
- Services spin down after 15 min inactivity (30s cold start)
- Starter tier: 0.5 CPU, 512 MB RAM (upgrade to Starter Pro for production)
- No paid addons included with free tier

## Support
See `docs/operations/RENDER_DEPLOYMENT_GUIDE.md` for troubleshooting and detailed instructions.
