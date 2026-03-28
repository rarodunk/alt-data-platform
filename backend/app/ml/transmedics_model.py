"""
TransMedics model — target: revenue_m.
Structural break in Q1 2023 (aviation segment launch).
Flight tracking from real TMDX fleet (34 aircraft, 21 active).
"""
import logging
from typing import Dict, Optional, Tuple
import pandas as pd
from .base_model import BaseForecaster
from .feature_engineering import build_features
from .backtester import run_backtest
from .forecast_utils import multi_quarter_forecast

logger = logging.getLogger(__name__)

STRUCTURAL_BREAK = "2023Q1"


class TransMedicsRevenueModel(BaseForecaster):
    def __init__(self):
        super().__init__(target_col="revenue_m", min_train_quarters=4)

    def prepare_features(self, actuals_df: pd.DataFrame,
                         trend_signals: Optional[pd.DataFrame] = None,
                         flight_signals: Optional[pd.DataFrame] = None,
                         alt_signals: Optional[pd.DataFrame] = None,
                         stock_signals: Optional[pd.DataFrame] = None, **_) -> Tuple[pd.DataFrame, pd.Series]:
        df = actuals_df[actuals_df["revenue_m"].notna()].copy()
        X = build_features(df, "revenue_m", trend_signals=trend_signals,
                           flight_signals=flight_signals,
                           alt_signals=alt_signals,
                           stock_signals=stock_signals,
                           structural_break_quarter=STRUCTURAL_BREAK)
        y = df["revenue_m"].reset_index(drop=True)
        return X, y


def run_transmedics_backtest(actuals_df: pd.DataFrame,
                             trend_signals: Optional[pd.DataFrame] = None,
                             flight_signals: Optional[pd.DataFrame] = None,
                             alt_signals: Optional[pd.DataFrame] = None,
                             stock_signals: Optional[pd.DataFrame] = None) -> Dict:
    df = actuals_df[actuals_df["revenue_m"].notna()].copy().reset_index(drop=True)
    # Filter to post-structural-break data only (Q1 2023+).
    # Pre-break revenue (~10-17M) is a completely different regime from
    # post-aviation-launch (~40-184M) and ruins the backtest.
    df["_period"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
    df = df[df["_period"] >= STRUCTURAL_BREAK].drop(columns=["_period"]).reset_index(drop=True)
    if len(df) < 5:
        return {"revenue_m": {"results": [], "metrics": {}}}
    tmp = TransMedicsRevenueModel()
    X, _ = tmp.prepare_features(df, trend_signals, flight_signals, alt_signals, stock_signals)
    return {"revenue_m": run_backtest(df, X, "revenue_m",
                                     model_factory=TransMedicsRevenueModel, min_train_quarters=4)}


def get_transmedics_forecast(actuals_df: pd.DataFrame,
                              trend_signals: Optional[pd.DataFrame] = None,
                              flight_signals: Optional[pd.DataFrame] = None,
                              alt_signals: Optional[pd.DataFrame] = None,
                              stock_signals: Optional[pd.DataFrame] = None,
                              horizons: int = 4) -> Dict:
    df = actuals_df[actuals_df["revenue_m"].notna()].copy().reset_index(drop=True)
    if len(df) < 4:
        return {}
    fwd = multi_quarter_forecast(
        TransMedicsRevenueModel, df, "revenue_m", horizons=horizons,
        trend_signals=trend_signals, flight_signals=flight_signals,
        alt_signals=alt_signals, stock_signals=stock_signals,
        structural_break_quarter=STRUCTURAL_BREAK,
    )
    model = TransMedicsRevenueModel()
    X, y = model.prepare_features(df, trend_signals, flight_signals, alt_signals, stock_signals)
    model.fit(X, y)
    return {"revenue_m": {"forward": fwd, "feature_importance": model.feature_importance()}}
