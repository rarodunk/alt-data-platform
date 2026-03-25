"""
Data seeding and refresh orchestration.
"""
import json
import logging
import os
from datetime import datetime
from typing import List, Optional

import pandas as pd

from ..database import SessionLocal
from ..models.db_models import ActualMetric, AltDataPoint, BacktestResult, ModelRun, RefreshLog

logger = logging.getLogger(__name__)

SEED_DIR = os.path.join(os.path.dirname(__file__), "../data/seed")

COMPANY_SEEDS = {
    "duolingo": "duolingo_actuals.json",
    "lemonade": "lemonade_actuals.json",
    "nu": "nu_actuals.json",
    "transmedics": "transmedics_actuals.json",
}


def seed_historical_data():
    """Load seed data from JSON files if not already loaded."""
    db = SessionLocal()
    try:
        for company, filename in COMPANY_SEEDS.items():
            filepath = os.path.join(SEED_DIR, filename)
            if not os.path.exists(filepath):
                logger.warning(f"Seed file not found: {filepath}")
                continue

            with open(filepath) as f:
                records = json.load(f)

            inserted = 0
            for record in records:
                if company == "duolingo":
                    metrics = [
                        ("revenue_m", record.get("revenue_m")),
                        ("dau_m", record.get("dau_m")),
                    ]
                elif company == "lemonade":
                    metrics = [("customers_k", record.get("customers_k"))]
                elif company == "nu":
                    metrics = [("customers_m", record.get("customers_m"))]
                elif company == "transmedics":
                    metrics = [("revenue_m", record.get("revenue_m"))]
                else:
                    metrics = []

                for metric_name, value in metrics:
                    if value is None:
                        continue
                    existing = (
                        db.query(ActualMetric)
                        .filter_by(company=company, quarter=record["quarter"], metric_name=metric_name)
                        .first()
                    )
                    if existing:
                        # Upsert: update if value changed (estimate → actual)
                        new_val = float(value)
                        new_src = record.get("source", "manual")
                        if abs(existing.value - new_val) > 0.001 or existing.source != new_src:
                            existing.value = new_val
                            existing.source = new_src
                            inserted += 1
                    else:
                        db.add(
                            ActualMetric(
                                company=company,
                                quarter=record["quarter"],
                                period_end=record["period_end"],
                                metric_name=metric_name,
                                value=float(value),
                                source=record.get("source", "manual"),
                                created_at=datetime.utcnow(),
                            )
                        )
                        inserted += 1

            db.commit()
            logger.info(f"Seeded {inserted} records for {company}")

    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()


def get_actuals_df(company: str, metric_name: Optional[str] = None) -> pd.DataFrame:
    """Return actuals as a DataFrame sorted by period_end."""
    db = SessionLocal()
    try:
        q = db.query(ActualMetric).filter(ActualMetric.company == company)
        if metric_name:
            q = q.filter(ActualMetric.metric_name == metric_name)
        rows = q.all()
        if not rows:
            return pd.DataFrame()
        data = [
            {
                "quarter": r.quarter,
                "period_end": r.period_end,
                "metric_name": r.metric_name,
                "value": r.value,
                "source": r.source,
            }
            for r in rows
        ]
        df = pd.DataFrame(data)
        df = df.sort_values("period_end").reset_index(drop=True)
        return df
    finally:
        db.close()


def get_wide_actuals_df(company: str) -> pd.DataFrame:
    """Return actuals pivoted so each metric is its own column."""
    df = get_actuals_df(company)
    if df.empty:
        return df
    pivoted = df.pivot_table(index=["quarter", "period_end"], columns="metric_name", values="value")
    pivoted = pivoted.reset_index().sort_values("period_end").reset_index(drop=True)
    pivoted.columns.name = None
    return pivoted


def save_backtest_results(company: str, metric_name: str, results: List[dict]):
    """Persist backtest results to DB (replacing existing for this company+metric)."""
    db = SessionLocal()
    try:
        db.query(BacktestResult).filter_by(company=company, metric_name=metric_name).delete()
        for r in results:
            db.add(
                BacktestResult(
                    company=company,
                    metric_name=metric_name,
                    quarter=r["quarter"],
                    actual_value=r["actual_value"],
                    predicted_value=r["predicted_value"],
                    error=r.get("error"),
                    pct_error=r.get("pct_error"),
                    created_at=datetime.utcnow(),
                )
            )
        db.commit()
        logger.info(f"Saved {len(results)} backtest results for {company}/{metric_name}")
    except Exception as e:
        logger.error(f"Error saving backtest results: {e}")
        db.rollback()
    finally:
        db.close()


def save_model_run(company: str, metric_name: str, metrics: dict, fi: dict, model_type: str = "ensemble"):
    db = SessionLocal()
    try:
        db.add(
            ModelRun(
                company=company,
                metric_name=metric_name,
                run_at=datetime.utcnow(),
                model_type=model_type,
                mae=metrics.get("mae"),
                mape=metrics.get("mape"),
                rmse=metrics.get("rmse"),
                directional_accuracy=metrics.get("directional_accuracy"),
                feature_importance=fi,
            )
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error saving model run: {e}")
        db.rollback()
    finally:
        db.close()


def save_alt_data_points(company: str, source_name: str, data_points: List[dict]):
    """Upsert alt data points."""
    if not data_points:
        return
    db = SessionLocal()
    try:
        for point in data_points:
            date_str = point.get("date", "")
            # Use first numeric field as metric value
            for metric_name, value in point.items():
                if metric_name in ("date", "company", "source", "subreddit", "keyword", "source_name"):
                    continue
                if not isinstance(value, (int, float)):
                    continue
                existing = (
                    db.query(AltDataPoint)
                    .filter_by(company=company, source_name=source_name, date=date_str, metric_name=metric_name)
                    .first()
                )
                if not existing:
                    db.add(
                        AltDataPoint(
                            company=company,
                            source_name=source_name,
                            date=date_str,
                            metric_name=metric_name,
                            value=float(value),
                            raw_value=float(value),
                            created_at=datetime.utcnow(),
                        )
                    )
        db.commit()
    except Exception as e:
        logger.error(f"Error saving alt data for {company}/{source_name}: {e}")
        db.rollback()
    finally:
        db.close()


def seed_signal_data():
    """
    Seed App Store historical estimates and TransMedics flight proxy data.
    Also purges stale zero-value Reddit placeholder records.
    Skips sources that already have data to avoid redundant work.
    """
    from ..connectors.appstore_connector import AppStoreConnector
    from ..connectors.opensky_connector import OpenSkyConnector

    companies = ["duolingo", "lemonade", "nu", "transmedics"]
    db = SessionLocal()

    try:
        # ── Purge Wikipedia data (not a useful signal source) ─────────────────
        wiki_count = db.query(AltDataPoint).filter(AltDataPoint.source_name == "wikipedia").count()
        if wiki_count > 0:
            db.query(AltDataPoint).filter(AltDataPoint.source_name == "wikipedia").delete()
            db.commit()
            logger.info(f"[seed_signals] Purged {wiki_count} Wikipedia records")

        # ── Purge stale zero-value Reddit placeholder data ─────────────────────
        zero_reddit = (
            db.query(AltDataPoint)
            .filter(AltDataPoint.source_name.in_(["reddit", "reddit_placeholder"]),
                    AltDataPoint.value == 0.0)
            .count()
        )
        if zero_reddit > 0:
            db.query(AltDataPoint).filter(
                AltDataPoint.source_name.in_(["reddit", "reddit_placeholder"]),
                AltDataPoint.value == 0.0,
            ).delete()
            db.commit()
            logger.info(f"[seed_signals] Purged {zero_reddit} zero-value Reddit placeholders")

        for company in companies:
            # ── App Store historical ───────────────────────────────────────────
            existing_app = (
                db.query(AltDataPoint)
                .filter_by(company=company, source_name="appstore")
                .first()
            )
            if not existing_app:
                try:
                    ac = AppStoreConnector()
                    hist = ac.get_historical_weekly(company)
                    if hist:
                        save_alt_data_points(company, "appstore", hist)
                        logger.info(f"[seed_signals] Saved {len(hist)} App Store records for {company}")
                except Exception as e:
                    logger.error(f"[seed_signals] App Store seed failed for {company}: {e}")

        # ── TransMedics flight proxy ───────────────────────────────────────────
        # Purge zero-value opensky records (live API can return empty flights, leaving zeroes)
        zero_opensky = (
            db.query(AltDataPoint)
            .filter(
                AltDataPoint.company == "transmedics",
                AltDataPoint.source_name == "opensky",
                AltDataPoint.metric_name == "flight_count",
                AltDataPoint.value == 0.0,
            )
            .count()
        )
        if zero_opensky > 0:
            db.query(AltDataPoint).filter(
                AltDataPoint.company == "transmedics",
                AltDataPoint.source_name == "opensky",
            ).delete()
            db.commit()
            logger.info(f"[seed_signals] Purged {zero_opensky} zero-value OpenSky records — will reseed with proxy")

        existing_flights = (
            db.query(AltDataPoint)
            .filter_by(company="transmedics", source_name="opensky_proxy")
            .first()
        )
        existing_live = (
            db.query(AltDataPoint)
            .filter_by(company="transmedics", source_name="opensky")
            .first()
        )
        if not existing_flights and not existing_live:
            try:
                oc = OpenSkyConnector()
                # Use proxy directly — live API requires 1100+ requests and takes 10+ min
                flight_data = oc._proxy(weeks_back=208)
                if flight_data:
                    save_alt_data_points("transmedics", "opensky_proxy", flight_data)
                    logger.info(f"[seed_signals] Saved {len(flight_data)} flight proxy records for transmedics")
            except Exception as e:
                logger.error(f"[seed_signals] OpenSky seed failed: {e}")

    finally:
        db.close()


def log_refresh(company: str, source_name: str, success: bool, records: int = 0, error: str = None):
    db = SessionLocal()
    try:
        db.add(
            RefreshLog(
                company=company,
                source_name=source_name,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                success=success,
                records_fetched=records,
                error_message=error,
            )
        )
        db.commit()
    except Exception as e:
        logger.error(f"Error logging refresh: {e}")
        db.rollback()
    finally:
        db.close()
