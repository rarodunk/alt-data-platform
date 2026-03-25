"""
Orchestration service: run models, return structured data for API endpoints.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from ..database import SessionLocal
from ..models.db_models import AltDataPoint, BacktestResult, ModelRun, Prediction, RefreshLog
from .data_refresh import (
    get_wide_actuals_df,
    save_alt_data_points,
    save_backtest_results,
    save_model_run,
    log_refresh,
)

logger = logging.getLogger(__name__)

COMPANY_META = {
    "duolingo": {
        "name": "Duolingo",
        "ticker": "DUOL",
        "description": "Language-learning app; predicting quarterly Revenue and DAUs.",
        "metrics": ["revenue_m", "dau_m"],
    },
    "lemonade": {
        "name": "Lemonade",
        "ticker": "LMND",
        "description": "InsurTech company; predicting customer count.",
        "metrics": ["customers_k"],
    },
    "nu": {
        "name": "Nu Holdings",
        "ticker": "NU",
        "description": "Brazilian digital bank; predicting customer count.",
        "metrics": ["customers_m"],
    },
    "transmedics": {
        "name": "TransMedics",
        "ticker": "TMDX",
        "description": "Organ transplant logistics; predicting quarterly revenue + flight tracking.",
        "metrics": ["revenue_m"],
    },
}


def _get_trend_signals_df(company: str) -> Optional[pd.DataFrame]:
    """Fetch Google Trends quarterly aggregates, falling back to DB cache."""
    db = SessionLocal()
    try:
        rows = (
            db.query(AltDataPoint)
            .filter(AltDataPoint.company == company, AltDataPoint.source_name == "google_trends")
            .all()
        )
        if not rows:
            return None
        data = [{"date": r.date, "keyword": r.metric_name, "avg_interest": r.value} for r in rows]
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        agg = df.groupby(["quarter", "keyword"])["avg_interest"].mean().reset_index()
        return agg
    finally:
        db.close()


def _get_alt_signals_df(company: str) -> Optional[pd.DataFrame]:
    """
    Fetch non-Trends, non-OpenSky alt data (Reddit, App Store, etc.) and return a wide
    quarterly DataFrame with columns named {source}_{metric_name}, ready for feature_engineering.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(AltDataPoint)
            .filter(
                AltDataPoint.company == company,
                AltDataPoint.source_name.notin_(["google_trends", "opensky", "opensky_proxy"]),
            )
            .all()
        )
        if not rows:
            return None
        data = [
            {
                "date": r.date,
                "col": f"{r.source_name}_{r.metric_name}",
                "value": r.value,
            }
            for r in rows
        ]
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        agg = df.groupby(["quarter", "col"])["value"].mean().reset_index()
        wide = agg.pivot_table(index="quarter", columns="col", values="value").reset_index()
        wide.columns.name = None
        return wide
    finally:
        db.close()


def _get_stock_signals_df(company: str) -> Optional[pd.DataFrame]:
    """
    Fetch yfinance quarterly signals stored as AltDataPoint rows (source_name='yfinance').
    Returns wide DataFrame: quarter, price_return_1q, price_return_4q, volume_zscore, price_52w_pct.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(AltDataPoint)
            .filter(AltDataPoint.company == company, AltDataPoint.source_name == "yfinance_quarterly")
            .all()
        )
        if not rows:
            return None
        data = [{"date": r.date, "col": r.metric_name, "value": r.value} for r in rows]
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        agg = df.groupby(["quarter", "col"])["value"].mean().reset_index()
        wide = agg.pivot_table(index="quarter", columns="col", values="value").reset_index()
        wide.columns.name = None
        return wide
    finally:
        db.close()


def _get_flight_signals_df() -> Optional[pd.DataFrame]:
    db = SessionLocal()
    try:
        rows = (
            db.query(AltDataPoint)
            .filter(
                AltDataPoint.company == "transmedics",
                AltDataPoint.source_name.in_(["opensky", "opensky_proxy"]),
            )
            .all()
        )
        if not rows:
            return None
        data = [{"date": r.date, "metric_name": r.metric_name, "value": r.value} for r in rows]
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)
        pivot = df.pivot_table(index="quarter", columns="metric_name", values="value", aggfunc="sum").reset_index()
        pivot.columns.name = None
        return pivot
    finally:
        db.close()


def run_models_for_company(company: str) -> Dict:
    """Run ML models for a company and persist results. Returns forecast dict."""
    actuals_df = get_wide_actuals_df(company)
    if actuals_df.empty:
        logger.warning(f"No actuals for {company}")
        return {}

    trend_df = _get_trend_signals_df(company)
    alt_df = _get_alt_signals_df(company)
    stock_df = _get_stock_signals_df(company)

    if company == "duolingo":
        from ..ml.duolingo_model import run_duolingo_backtest, get_duolingo_forecast

        backtest = run_duolingo_backtest(actuals_df, trend_df, alt_df, stock_df)
        forecast = get_duolingo_forecast(actuals_df, trend_df, alt_df, stock_df)

    elif company == "lemonade":
        from ..ml.lemonade_model import run_lemonade_backtest, get_lemonade_forecast

        backtest = run_lemonade_backtest(actuals_df, trend_df, alt_df, stock_df)
        forecast = get_lemonade_forecast(actuals_df, trend_df, alt_df, stock_df)

    elif company == "nu":
        from ..ml.nu_model import run_nu_backtest, get_nu_forecast

        backtest = run_nu_backtest(actuals_df, trend_df, alt_df, stock_df)
        forecast = get_nu_forecast(actuals_df, trend_df, alt_df, stock_df)

    elif company == "transmedics":
        from ..ml.transmedics_model import run_transmedics_backtest, get_transmedics_forecast

        flight_df = _get_flight_signals_df()
        backtest = run_transmedics_backtest(actuals_df, trend_df, flight_df, alt_df, stock_df)
        forecast = get_transmedics_forecast(actuals_df, trend_df, flight_df, alt_df, stock_df)

    else:
        return {}

    # Persist backtest results and model runs
    for metric_name, bt in backtest.items():
        results_list = bt.get("results", [])
        metrics_dict = bt.get("metrics", {})
        if results_list:
            save_backtest_results(company, metric_name, results_list)
        if metrics_dict:
            fi = forecast.get(metric_name, {}).get("feature_importance", {})
            save_model_run(company, metric_name, metrics_dict, fi)

    # Persist all forward predictions (multiple horizons)
    db = SessionLocal()
    try:
        run_ts = datetime.utcnow()
        for metric_name, fc in forecast.items():
            if not fc:
                continue
            forward_list = fc.get("forward", [])
            fi_keys = list(fc.get("feature_importance", {}).keys())[:10]

            for pred in forward_list:
                # Check for existing prediction for this quarter (upsert by quarter+metric+company)
                existing = (
                    db.query(Prediction)
                    .filter_by(company=company, metric_name=metric_name, quarter=pred["quarter"])
                    .first()
                )
                if existing:
                    existing.predicted_value = pred["predicted_value"]
                    existing.confidence_lower = pred["confidence_lower"]
                    existing.confidence_upper = pred["confidence_upper"]
                    existing.created_at = run_ts
                else:
                    db.add(Prediction(
                        company=company,
                        metric_name=metric_name,
                        quarter=pred["quarter"],
                        period_end=pred["period_end"],
                        predicted_value=pred["predicted_value"],
                        confidence_lower=pred["confidence_lower"],
                        confidence_upper=pred["confidence_upper"],
                        model_version=f"ensemble_v2_h{pred['horizon']}",
                        features_used=fi_keys,
                        created_at=run_ts,
                    ))
        db.commit()
    except Exception as e:
        logger.error(f"Error persisting predictions: {e}")
        db.rollback()
    finally:
        db.close()

    return forecast


def _quarter_to_period_end(quarter_label: str) -> str:
    """Convert 'Q1 2025' -> '2025-03-31'."""
    quarter_ends = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}
    parts = quarter_label.strip().split()
    if len(parts) == 2:
        q, year = parts
        suffix = quarter_ends.get(q, "12-31")
        return f"{year}-{suffix}"
    return ""


def get_company_overview(company: str) -> Dict:
    """Return full company data for the API overview endpoint."""
    db = SessionLocal()
    try:
        meta = COMPANY_META.get(company, {})

        # Actuals
        from ..models.db_models import ActualMetric

        actual_rows = (
            db.query(ActualMetric)
            .filter(ActualMetric.company == company)
            .order_by(ActualMetric.period_end)
            .all()
        )
        actuals = [
            {
                "quarter": r.quarter,
                "period_end": r.period_end,
                "metric_name": r.metric_name,
                "value": r.value,
                "source": r.source,
            }
            for r in actual_rows
        ]

        # All forward predictions sorted chronologically
        all_preds = (
            db.query(Prediction)
            .filter(Prediction.company == company)
            .order_by(Prediction.period_end.asc(), Prediction.created_at.desc())
            .all()
        )
        # Deduplicate by (metric_name, quarter) — keep most recent run
        seen_pred_keys = set()
        forward_preds = []
        for p in all_preds:
            key = (p.metric_name, p.quarter)
            if key not in seen_pred_keys:
                forward_preds.append(p)
                seen_pred_keys.add(key)

        # Latest = nearest quarter per metric, previous = second nearest
        latest_preds_by_metric: Dict[str, object] = {}
        prev_preds_by_metric: Dict[str, object] = {}
        for p in forward_preds:
            if p.metric_name not in latest_preds_by_metric:
                latest_preds_by_metric[p.metric_name] = p
            elif p.metric_name not in prev_preds_by_metric:
                prev_preds_by_metric[p.metric_name] = p
        latest_preds = list(latest_preds_by_metric.values())
        prev_preds = list(prev_preds_by_metric.values())

        def pred_to_dict(p):
            return {
                "quarter": p.quarter,
                "period_end": p.period_end,
                "metric_name": p.metric_name,
                "predicted_value": p.predicted_value,
                "confidence_lower": p.confidence_lower,
                "confidence_upper": p.confidence_upper,
                "model_version": p.model_version,
                "created_at": str(p.created_at),
            }

        # Backtest results
        bt_rows = (
            db.query(BacktestResult)
            .filter(BacktestResult.company == company)
            .order_by(BacktestResult.quarter)
            .all()
        )
        backtest_results = [
            {
                "quarter": r.quarter,
                "metric_name": r.metric_name,
                "actual_value": r.actual_value,
                "predicted_value": r.predicted_value,
                "error": r.error,
                "pct_error": r.pct_error,
            }
            for r in bt_rows
        ]

        # Model metrics (latest run per metric)
        model_runs = {}
        mr_rows = (
            db.query(ModelRun)
            .filter(ModelRun.company == company)
            .order_by(ModelRun.run_at.desc())
            .all()
        )
        seen_mr = set()
        for mr in mr_rows:
            if mr.metric_name not in seen_mr:
                model_runs[mr.metric_name] = {
                    "mae": mr.mae,
                    "mape": mr.mape,
                    "rmse": mr.rmse,
                    "directional_accuracy": mr.directional_accuracy,
                    "feature_importance": mr.feature_importance or {},
                    "model_type": mr.model_type,
                    "run_at": str(mr.run_at),
                }
                seen_mr.add(mr.metric_name)

        # Alt data signals — fetch all, ordered by date ascending for frontend correlation
        signal_rows = (
            db.query(AltDataPoint)
            .filter(AltDataPoint.company == company)
            .order_by(AltDataPoint.date.asc())
            .all()
        )
        signals = [
            {
                "date": r.date,
                "value": r.value,
                "source": r.source_name,
                "metric_name": r.metric_name,
            }
            for r in signal_rows
        ]

        # Refresh logs
        rl_rows = (
            db.query(RefreshLog)
            .filter(RefreshLog.company == company)
            .order_by(RefreshLog.started_at.desc())
            .limit(20)
            .all()
        )
        refresh_logs = [
            {
                "source_name": r.source_name,
                "started_at": str(r.started_at),
                "completed_at": str(r.completed_at) if r.completed_at else None,
                "success": r.success,
                "records_fetched": r.records_fetched,
                "error_message": r.error_message,
            }
            for r in rl_rows
        ]

        last_refreshed = None
        if rl_rows:
            last_refreshed = str(rl_rows[0].completed_at or rl_rows[0].started_at)

        return {
            "company": company,
            "name": meta.get("name", company),
            "ticker": meta.get("ticker", ""),
            "description": meta.get("description", ""),
            "last_refreshed": last_refreshed,
            "actuals": actuals,
            "latest_predictions": [pred_to_dict(p) for p in latest_preds],
            "previous_predictions": [pred_to_dict(p) for p in prev_preds],
            "forward_predictions": [pred_to_dict(p) for p in forward_preds],
            "backtest_results": backtest_results,
            "model_metrics": model_runs,
            "signals": signals,
            "refresh_log": refresh_logs,
        }

    finally:
        db.close()


def trigger_refresh(company: str) -> Dict:
    """
    Fetch fresh alt data and re-run models.
    Returns a summary of what was done.
    """
    summary = {"company": company, "steps": []}

    # 1. Google Trends
    try:
        from ..connectors.google_trends import GoogleTrendsConnector

        gt = GoogleTrendsConnector()
        data = gt.fetch_with_cache(company=company)
        save_alt_data_points(company, "google_trends", data)
        log_refresh(company, "google_trends", success=True, records=len(data))
        summary["steps"].append({"source": "google_trends", "records": len(data), "ok": True})
    except Exception as e:
        log_refresh(company, "google_trends", success=False, error=str(e))
        summary["steps"].append({"source": "google_trends", "ok": False, "error": str(e)})

    # 2. Reddit
    try:
        from ..connectors.reddit_connector import RedditConnector

        rc = RedditConnector()
        reddit_data = rc.fetch_with_cache(company=company)
        save_alt_data_points(company, "reddit", reddit_data)
        log_refresh(company, "reddit", success=True, records=len(reddit_data))
        summary["steps"].append({"source": "reddit", "records": len(reddit_data), "ok": True})
    except Exception as e:
        log_refresh(company, "reddit", success=False, error=str(e))
        summary["steps"].append({"source": "reddit", "ok": False, "error": str(e)})

    # 3. App Store (current snapshot)
    try:
        from ..connectors.appstore_connector import AppStoreConnector

        ac = AppStoreConnector()
        app_data = ac.fetch_with_cache(company=company)
        if app_data:
            save_alt_data_points(company, "appstore", app_data)
        log_refresh(company, "appstore", success=True, records=len(app_data))
        summary["steps"].append({"source": "appstore", "records": len(app_data), "ok": True})
    except Exception as e:
        log_refresh(company, "appstore", success=False, error=str(e))
        summary["steps"].append({"source": "appstore", "ok": False, "error": str(e)})

    # 4. yfinance — stock price momentum signals
    try:
        from ..connectors.yfinance_connector import YFinanceConnector

        yf_conn = YFinanceConnector()
        quarterly_signals = yf_conn.fetch_quarterly_signals(company=company)
        if quarterly_signals:
            # Build one row per quarter with all signal columns (save_alt_data_points iterates keys)
            flat_points = []
            for sig in quarterly_signals:
                q_label = sig["quarter"]  # e.g. "2024Q3"
                try:
                    period = pd.Period(q_label, freq="Q")
                    date_str = str(period.end_time.date())
                except Exception:
                    date_str = q_label
                row = {"date": date_str, "company": company, "source": "yfinance_quarterly"}
                row.update({k: v for k, v in sig.items() if k != "quarter"})
                flat_points.append(row)
            save_alt_data_points(company, "yfinance_quarterly", flat_points)
        log_refresh(company, "yfinance", success=True, records=len(quarterly_signals))
        summary["steps"].append({"source": "yfinance", "records": len(quarterly_signals), "ok": True})
    except Exception as e:
        log_refresh(company, "yfinance", success=False, error=str(e))
        summary["steps"].append({"source": "yfinance", "ok": False, "error": str(e)})

    # 5. SEC EDGAR — pull latest 10-Q revenue actuals and upsert
    try:
        from ..connectors.sec_edgar_connector import SECEdgarConnector

        edgar = SECEdgarConnector()
        edgar_records = edgar.get_revenue_actuals(company)
        if edgar_records:
            from ..database import SessionLocal as _SL
            from ..models.db_models import ActualMetric
            from datetime import datetime as _dt
            db = _SL()
            upserted = 0
            try:
                for rec in edgar_records:
                    existing = (
                        db.query(ActualMetric)
                        .filter_by(company=company, quarter=rec["quarter"], metric_name="revenue_m")
                        .first()
                    )
                    new_val = float(rec["revenue_m"])
                    if existing:
                        if abs(existing.value - new_val) > 0.01:
                            existing.value = new_val
                            existing.source = rec["source"]
                            upserted += 1
                    else:
                        db.add(ActualMetric(
                            company=company,
                            quarter=rec["quarter"],
                            period_end=rec["period_end"],
                            metric_name="revenue_m",
                            value=new_val,
                            source=rec["source"],
                            created_at=_dt.utcnow(),
                        ))
                        upserted += 1
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
            log_refresh(company, "sec_edgar", success=True, records=upserted)
            summary["steps"].append({"source": "sec_edgar", "records": upserted, "ok": True})
        else:
            summary["steps"].append({"source": "sec_edgar", "records": 0, "ok": True, "note": "no data"})
    except Exception as e:
        log_refresh(company, "sec_edgar", success=False, error=str(e))
        summary["steps"].append({"source": "sec_edgar", "ok": False, "error": str(e)})

    # 6. OpenSky (TransMedics only)
    if company == "transmedics":
        try:
            from ..connectors.opensky_connector import OpenSkyConnector

            oc = OpenSkyConnector()
            # Use proxy directly — live API needs 1000+ requests and gets rate-limited
            flight_data = oc._proxy(weeks_back=104)
            save_alt_data_points(company, "opensky_proxy", flight_data)
            log_refresh(company, "opensky", success=True, records=len(flight_data))
            summary["steps"].append({"source": "opensky", "records": len(flight_data), "ok": True})
        except Exception as e:
            log_refresh(company, "opensky", success=False, error=str(e))
            summary["steps"].append({"source": "opensky", "ok": False, "error": str(e)})

    # 7. Re-run models
    try:
        forecast = run_models_for_company(company)
        summary["forecast"] = {k: {"predicted_value": v.get("predicted_value")} for k, v in forecast.items()}
        summary["models_run"] = True
    except Exception as e:
        logger.error(f"Model run failed for {company}: {e}")
        summary["models_run"] = False
        summary["model_error"] = str(e)

    return summary
