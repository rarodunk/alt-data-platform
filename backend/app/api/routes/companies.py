"""
Main API routes for all companies.
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ...database import SessionLocal
from ...models.db_models import ActualMetric, BacktestResult, ModelRun, RefreshLog
from ...services.prediction_service import (
    COMPANY_META,
    get_company_overview,
    run_models_for_company,
    trigger_refresh,
)

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_COMPANIES = list(COMPANY_META.keys())


def _validate_company(company: str):
    if company not in VALID_COMPANIES:
        raise HTTPException(status_code=404, detail=f"Company '{company}' not found. Valid: {VALID_COMPANIES}")


# ---------------------------------------------------------------------------
# /api/companies
# ---------------------------------------------------------------------------
@router.get("/companies")
def list_companies():
    """Return all companies with metadata and last refresh time."""
    db = SessionLocal()
    try:
        result = []
        for company, meta in COMPANY_META.items():
            last_refresh = (
                db.query(RefreshLog)
                .filter(RefreshLog.company == company)
                .order_by(RefreshLog.started_at.desc())
                .first()
            )
            last_prediction = (
                db.query(BacktestResult)
                .filter(BacktestResult.company == company)
                .first()
            )
            result.append(
                {
                    "id": company,
                    "name": meta["name"],
                    "ticker": meta["ticker"],
                    "description": meta["description"],
                    "metrics": meta["metrics"],
                    "lastRefreshed": str(last_refresh.completed_at) if last_refresh and last_refresh.completed_at else None,
                    "hasModels": last_prediction is not None,
                }
            )
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /api/{company}/overview
# ---------------------------------------------------------------------------
@router.get("/{company}/overview")
def company_overview(company: str):
    _validate_company(company)
    # Run models on first call if no backtest results exist
    db = SessionLocal()
    try:
        has_results = db.query(BacktestResult).filter(BacktestResult.company == company).first()
    finally:
        db.close()

    if not has_results:
        logger.info(f"First call for {company} — running models now")
        try:
            run_models_for_company(company)
        except Exception as e:
            logger.error(f"Model run error for {company}: {e}")

    return get_company_overview(company)


# ---------------------------------------------------------------------------
# /api/{company}/actuals
# ---------------------------------------------------------------------------
@router.get("/{company}/actuals")
def company_actuals(company: str):
    _validate_company(company)
    db = SessionLocal()
    try:
        rows = (
            db.query(ActualMetric)
            .filter(ActualMetric.company == company)
            .order_by(ActualMetric.period_end)
            .all()
        )
        return [
            {
                "quarter": r.quarter,
                "period_end": r.period_end,
                "metric_name": r.metric_name,
                "value": r.value,
                "source": r.source,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /api/{company}/backtest
# ---------------------------------------------------------------------------
@router.get("/{company}/backtest")
def company_backtest(company: str, metric: Optional[str] = Query(None)):
    _validate_company(company)
    db = SessionLocal()
    try:
        q = db.query(BacktestResult).filter(BacktestResult.company == company)
        if metric:
            q = q.filter(BacktestResult.metric_name == metric)
        rows = q.order_by(BacktestResult.quarter).all()

        # Compute aggregate metrics
        results = [
            {
                "quarter": r.quarter,
                "metric_name": r.metric_name,
                "actual_value": r.actual_value,
                "predicted_value": r.predicted_value,
                "error": r.error,
                "pct_error": r.pct_error,
            }
            for r in rows
        ]

        # Get latest model run for metrics
        mr_q = db.query(ModelRun).filter(ModelRun.company == company)
        if metric:
            mr_q = mr_q.filter(ModelRun.metric_name == metric)
        mr_rows = mr_q.order_by(ModelRun.run_at.desc()).all()

        model_metrics = {}
        seen = set()
        for mr in mr_rows:
            if mr.metric_name not in seen:
                model_metrics[mr.metric_name] = {
                    "mae": mr.mae,
                    "mape": mr.mape,
                    "rmse": mr.rmse,
                    "directional_accuracy": mr.directional_accuracy,
                    "feature_importance": mr.feature_importance or {},
                    "n_quarters": len([r for r in results if r["metric_name"] == mr.metric_name]),
                }
                seen.add(mr.metric_name)

        return {"results": results, "metrics": model_metrics}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /api/{company}/signals
# ---------------------------------------------------------------------------
@router.get("/{company}/signals")
def company_signals(company: str):
    _validate_company(company)
    from ...models.db_models import AltDataPoint

    db = SessionLocal()
    try:
        rows = (
            db.query(AltDataPoint)
            .filter(AltDataPoint.company == company)
            .order_by(AltDataPoint.date.desc())
            .limit(2000)
            .all()
        )
        return [
            {
                "date": r.date,
                "value": r.value,
                "source": r.source_name,
                "metric_name": r.metric_name,
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /api/{company}/predictions
# ---------------------------------------------------------------------------
@router.get("/{company}/predictions")
def company_predictions(company: str):
    _validate_company(company)
    from ...models.db_models import Prediction

    db = SessionLocal()
    try:
        rows = (
            db.query(Prediction)
            .filter(Prediction.company == company)
            .order_by(Prediction.created_at.desc())
            .limit(50)
            .all()
        )
        return [
            {
                "quarter": r.quarter,
                "period_end": r.period_end,
                "metric_name": r.metric_name,
                "predicted_value": r.predicted_value,
                "confidence_lower": r.confidence_lower,
                "confidence_upper": r.confidence_upper,
                "model_version": r.model_version,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /api/{company}/refresh  (POST)
# ---------------------------------------------------------------------------
@router.post("/{company}/refresh")
def refresh_company(company: str, background_tasks: BackgroundTasks):
    _validate_company(company)
    background_tasks.add_task(_do_refresh, company)
    return {"status": "refresh_started", "company": company}


def _do_refresh(company: str):
    try:
        trigger_refresh(company)
    except Exception as e:
        logger.error(f"Background refresh failed for {company}: {e}")


# ---------------------------------------------------------------------------
# /api/{company}/refresh-status
# ---------------------------------------------------------------------------
@router.get("/{company}/refresh-status")
def refresh_status(company: str):
    _validate_company(company)
    db = SessionLocal()
    try:
        rows = (
            db.query(RefreshLog)
            .filter(RefreshLog.company == company)
            .order_by(RefreshLog.started_at.desc())
            .limit(10)
            .all()
        )
        return [
            {
                "source_name": r.source_name,
                "started_at": str(r.started_at),
                "completed_at": str(r.completed_at) if r.completed_at else None,
                "success": r.success,
                "records_fetched": r.records_fetched,
                "error_message": r.error_message,
            }
            for r in rows
        ]
    finally:
        db.close()
