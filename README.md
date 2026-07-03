# Loan Default Early Warning Project

This project helps MFIs and loan officers identify which currently regular (`STD`) loan accounts are most likely to become delinquent or default later, so they can act early and focus collections effort where it matters most.

## What this project does

- Cleans and validates your loan dataset.
- Engineers key risk features:
  - Arrear ratio
  - LTV ratio
  - Interest stress
  - Delinquency and installment risk scores
- Builds a rule-based risk score for immediate business use.
- Trains a Logistic Regression model if future labels are available (`FutureStatusCode`).
- Scores currently regular accounts and outputs top risk accounts.
- Generates daily officer visit plans for medium/high-risk accounts.
- Produces per-officer collection KPI summaries and coaching hints.
- Exports a field feedback template to capture next-day planning inputs.

## Why it is used

- To detect risky borrowers early, before the account becomes harder to recover.
- To help loan officers prioritize the right cases instead of reviewing every account manually.
- To reduce collection cost and travel time by turning data into an action list.
- To support a more consistent, less reactive, and more auditable collections process.

## Expected input file

For development, use the included dummy input file:

- `data/raw/Loan Accounts-Dummy.csv`

Required columns:

- `CLStatusCode`
- `AgeDays`
- `DefaultedInst`
- `PrincipalOS`
- `PrincipalArrear`
- `InterestArrear`
- `TotalAccruedInt`
- `SecurityValue`
- `Sector`

Optional but recommended:

- `RepaymentFrequency`
- `FutureStatusCode` (needed for supervised ML training)
- `TotalInstallments`
- `Branch`

Runtime entry points:

- `python run_pipeline.py` to generate processed data, scores, and operational outputs
- `python run_api.py` to serve the FastAPI API
- `streamlit run app.py` to open the dashboard

In the dashboard, use the sidebar upload control to replace the active input file and run the pipeline from the UI.

## Security configuration

The API supports environment-driven security settings:

- `SECRET_KEY`: JWT signing key. Required for production (`APP_ENV=production`).
- `APP_ENV`: `development` (default) or `production`.
- `CORS_ALLOW_ORIGINS`: comma-separated trusted origins (default: `http://localhost:3000,http://localhost:8501`).
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`: admin credentials for demo auth.
- `ENABLE_DEMO_OFFICER_USER`: set to `false` to disable the seeded officer user.
- `OFFICER_USERNAME`, `OFFICER_PASSWORD`: optional demo officer credentials.

## Quick start

```powershell
cd loan-default-risk-project
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run_pipeline.py
```

The pipeline will read the dummy CSV by default. Replace it later with your real branch or MFI data when you are ready.

## Outputs

- `data/processed/loan_accounts_processed.csv`
- `outputs/scored_accounts.csv`
- `outputs/top_risky_accounts.csv`
- `outputs/model_metrics.json` (only if `FutureStatusCode` exists)
- `models/default_risk_model.joblib` (only if `FutureStatusCode` exists)
- `outputs/daily_visit_plan.csv`
- `outputs/officer_kpis.csv`
- `outputs/field_feedback_template.csv`

## Risk logic used

Rule score:

- DelinquencyScore * 30
- InstallmentRisk * 25
- LTVRatio > 0.8 -> +20 else +10
- ArrearRatio > 0.3 -> +25 else +10

Rule categories:

- High Risk: score >= 70
- Medium Risk: score >= 40 and < 70
- Low Risk: score < 40

## Notes

- If `FutureStatusCode` is not present, the pipeline still works in rule-based mode.
- To get model-based default probability, include `FutureStatusCode` in historical data.
