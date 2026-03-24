# Alt Data Platform

Alternative data forecasting platform for DUOL, LMND, NU, and TMDX.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Alt Data Platform                        │
│                                                                 │
│  Frontend (Next.js 14)     ──►  Backend (FastAPI / Python)      │
│  localhost:3000                 localhost:8000                  │
│                                                                 │
│  Pages:                         API:                            │
│  / (dashboard)                  GET  /api/companies             │
│  /duolingo                      GET  /api/{co}/overview         │
│  /lemonade                      GET  /api/{co}/actuals          │
│  /nu                            GET  /api/{co}/backtest         │
│  /transmedics                   GET  /api/{co}/signals          │
│                                 POST /api/{co}/refresh          │
│                                                                 │
│  Components:                    ML Layer:                       │
│  ForecastCards                  Ridge / ElasticNet              │
│  SignalDashboard                XGBoost                         │
│  BacktestSection                LightGBM (optional)             │
│  ModelDiagnostics               Ensemble mean                   │
│  RefreshPanel                   Walk-forward backtest           │
│                                                                 │
│  Data Sources:                  Database:                       │
│  Google Trends (pytrends)       SQLite (altdata.db)             │
│  Reddit (PRAW)                  SQLAlchemy ORM                  │
│  OpenSky Network                                                │
│  Seed JSON files                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and enter
cd /Users/ryanreeves/alt-data-platform

# 2. Copy environment file
cp .env.example backend/.env

# 3. Run everything
./start.sh
```

Then open http://localhost:3000.

## Manual Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # edit as needed
uvicorn main:app --reload --port 8000
```

The backend auto-seeds the SQLite database from the JSON files in
`backend/app/data/seed/` on first startup, then runs models for all
four companies.

### Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local
npm run dev
```

## Data Source Status

| Source | Status | Notes |
|--------|--------|-------|
| Historical seed data | Implemented | JSON files in `backend/app/data/seed/` |
| Google Trends | Implemented | Free via pytrends, no auth required |
| Reddit | Requires API Key | Set `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` in `.env` |
| OpenSky (flights) | Requires Setup | Set `TMDX_AIRCRAFT_ICAO24` — see below |

## Historical Data Sources

All seed data comes from SEC filings. Verify at:
- **Duolingo (DUOL)**: https://investors.duolingo.com
- **Lemonade (LMND)**: https://ir.lemonade.com
- **Nu Holdings (NU)**: https://ir.nu.com.br
- **TransMedics (TMDX)**: https://ir.transmedics.com

## Flight Tracking Setup (TransMedics)

1. Go to https://registry.faa.gov/AircraftInquiry/
2. Search by **Owner** for "TransMedics"
3. Note the N-numbers (e.g., N189TM)
4. Convert to ICAO24 hex: use https://www.faa.gov/licenses_certificates/aircraft_certification/aircraft_registry/releasable_aircraft_download or online tools
5. Add to `backend/.env`:
   ```
   TMDX_AIRCRAFT_ICAO24=hex1,hex2,hex3
   ```

## Reddit API Setup

1. Go to https://www.reddit.com/prefs/apps
2. Create a "script" application
3. Add to `backend/.env`:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_secret
   ```

## Model Architecture

Each company uses an **ensemble forecaster**:

- **Ridge Regression** (with StandardScaler)
- **ElasticNet** (with StandardScaler)
- **XGBoost** (tree-based, no scaling)
- **LightGBM** (tree-based, no scaling) — requires `libomp` on macOS

Point forecast = mean of all models. Confidence interval = mean ± 1.5σ.

### Features

- Lag values: t-1, t-2, t-3, t-4 quarters
- Rolling means: 2Q and 4Q windows
- Growth rates: QoQ and YoY
- Linear trend index
- Quarter-of-year dummies (Q1–Q4)
- Google Trends lagged signals
- Flight utilization (TransMedics)
- Structural break dummy (TransMedics, Q1 2023)

### Validation

Walk-forward backtesting (no look-ahead bias):
- Train on [0..t], predict t+1
- Minimum 4–6 quarters of training data
- Metrics: MAE, MAPE, RMSE, Directional Accuracy

## Adding a New Company

1. Add seed JSON to `backend/app/data/seed/newco_actuals.json`
2. Add company to `COMPANY_META` in `backend/app/services/prediction_service.py`
3. Add company to `COMPANY_SEEDS` in `backend/app/services/data_refresh.py`
4. Create `backend/app/ml/newco_model.py` following the Lemonade model pattern
5. Wire it into `run_models_for_company()` in `prediction_service.py`
6. Add keywords to `COMPANY_KEYWORDS` in `backend/app/connectors/google_trends.py`
7. Add a frontend page at `frontend/src/app/newco/page.tsx`
8. Add nav link in `frontend/src/components/layout/Navbar.tsx`

## Known Limitations

- **LightGBM on macOS** requires `libomp` (`brew install libomp`). The platform
  degrades gracefully to Ridge + ElasticNet + XGBoost if it's missing.
- **Google Trends** rate-limits aggressively. The connector uses exponential
  backoff, but heavy use may result in temporary blocks.
- **Reddit data** reflects only the most recent ~100 "hot" posts per subreddit,
  not full historical data. This is a limitation of the free PRAW approach.
- **OpenSky** free tier has lower rate limits than the authenticated tier.
- **TransMedics ICAO24 codes** must be manually verified — the platform ships
  with no default codes to avoid tracking errors.
- Models use seed data only (no live earnings scraping). Update seed files
  after each earnings release.
