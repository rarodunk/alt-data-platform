import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alt Data Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _nightly_refresh():
    """Run a full refresh + model re-run for all companies. Called by APScheduler."""
    from app.services.prediction_service import trigger_refresh
    companies = ["duolingo", "lemonade", "nu", "transmedics"]
    for co in companies:
        try:
            logger.info(f"[scheduler] Starting nightly refresh for {co}")
            result = trigger_refresh(co)
            steps_ok = sum(1 for s in result.get("steps", []) if s.get("ok"))
            logger.info(f"[scheduler] {co} refresh done — {steps_ok}/{len(result.get('steps', []))} sources ok, models_run={result.get('models_run')}")
        except Exception as e:
            logger.error(f"[scheduler] Nightly refresh failed for {co}: {e}")


@app.on_event("startup")
async def startup():
    init_db()
    try:
        from app.services.data_refresh import seed_historical_data
        seed_historical_data()
    except Exception as e:
        logger.error(f"Actuals seed failed: {e}")
    try:
        from app.services.data_refresh import seed_signal_data
        seed_signal_data()
    except Exception as e:
        logger.error(f"Signal seed failed: {e}")

    # Start APScheduler — nightly refresh at 2 AM UTC
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            _nightly_refresh,
            trigger=CronTrigger(hour=2, minute=0),
            id="nightly_refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("APScheduler started — nightly refresh at 02:00 UTC")
    except Exception as e:
        logger.error(f"APScheduler failed to start: {e}")

    logger.info("Alt Data Platform started")


@app.on_event("shutdown")
async def shutdown():
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


from app.api.routes import companies  # noqa: E402

app.include_router(companies.router, prefix="/api")


@app.get("/health")
def health():
    scheduler = getattr(app.state, "scheduler", None)
    return {
        "status": "ok",
        "scheduler": "running" if scheduler and scheduler.running else "stopped",
    }
