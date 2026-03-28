"""
Duolingo forecasting model.  Targets: revenue_m and dau_m.
"""
import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .base_model import BaseForecaster
from .feature_engineering import build_features
from .backtester import run_backtest
from .forecast_utils import multi_quarter_forecast, build_next_row, _next_quarter

logger = logging.getLogger(__name__)


class DuolingoRevenueModel(BaseForecaster):
    def __init__(self):
        super().__init__(target_col="revenue_m", min_train_quarters=10)

    def prepare_features(self, actuals_df: pd.DataFrame,
                         trend_signals: Optional[pd.DataFrame] = None,
                         alt_signals: Optional[pd.DataFrame] = None,
                         stock_signals: Optional[pd.DataFrame] = None, **_) -> Tuple[pd.DataFrame, pd.Series]:
        df = actuals_df[actuals_df["revenue_m"].notna()].copy()
        X = build_features(df, "revenue_m", trend_signals=trend_signals,
                           alt_signals=alt_signals, stock_signals=stock_signals)
        y = df["revenue_m"].reset_index(drop=True)
        return X, y


class DuolingoDAUModel(BaseForecaster):
    def __init__(self):
        super().__init__(target_col="dau_m", min_train_quarters=6)

    def prepare_features(self, actuals_df: pd.DataFrame,
                         trend_signals: Optional[pd.DataFrame] = None,
                         alt_signals: Optional[pd.DataFrame] = None,
                         stock_signals: Optional[pd.DataFrame] = None, **_) -> Tuple[pd.DataFrame, pd.Series]:
        df = actuals_df[actuals_df["dau_m"].notna()].copy()
        X = build_features(df, "dau_m", trend_signals=trend_signals,
                           alt_signals=alt_signals, stock_signals=stock_signals)
        y = df["dau_m"].reset_index(drop=True)
        return X, y


def run_duolingo_backtest(actuals_df: pd.DataFrame,
                          trend_signals: Optional[pd.DataFrame] = None,
                          alt_signals: Optional[pd.DataFrame] = None,
                          stock_signals: Optional[pd.DataFrame] = None) -> Dict:
    results = {}
    rev_df = actuals_df[actuals_df["revenue_m"].notna()].copy().reset_index(drop=True)
    if len(rev_df) >= 11:
        tmp = DuolingoRevenueModel()
        X, _ = tmp.prepare_features(rev_df, trend_signals, alt_signals, stock_signals)
        results["revenue_m"] = run_backtest(rev_df, X, "revenue_m",
                                            model_factory=DuolingoRevenueModel, min_train_quarters=10)
    dau_df = actuals_df[actuals_df["dau_m"].notna()].copy().reset_index(drop=True)
    if len(dau_df) >= 7:
        tmp = DuolingoDAUModel()
        X, _ = tmp.prepare_features(dau_df, trend_signals, alt_signals, stock_signals)
        results["dau_m"] = run_backtest(dau_df, X, "dau_m",
                                        model_factory=DuolingoDAUModel, min_train_quarters=6)
    return results


def get_duolingo_forecast(actuals_df: pd.DataFrame,
                          trend_signals: Optional[pd.DataFrame] = None,
                          alt_signals: Optional[pd.DataFrame] = None,
                          stock_signals: Optional[pd.DataFrame] = None,
                          horizons: int = 4) -> Dict:
    """Forecast next `horizons` quarters for revenue and DAUs."""
    output = {}

    rev_df = actuals_df[actuals_df["revenue_m"].notna()].copy().reset_index(drop=True)
    if len(rev_df) >= 6:
        fwd = multi_quarter_forecast(
            DuolingoRevenueModel, rev_df, "revenue_m",
            horizons=horizons, trend_signals=trend_signals,
            alt_signals=alt_signals, stock_signals=stock_signals,
        )
        model = DuolingoRevenueModel()
        X, y = model.prepare_features(rev_df, trend_signals, alt_signals, stock_signals)
        model.fit(X, y)
        output["revenue_m"] = {"forward": fwd, "feature_importance": model.feature_importance()}

    dau_df = actuals_df[actuals_df["dau_m"].notna()].copy().reset_index(drop=True)
    if len(dau_df) >= 4:
        fwd = multi_quarter_forecast(
            DuolingoDAUModel, dau_df, "dau_m",
            horizons=horizons, trend_signals=trend_signals,
            alt_signals=alt_signals, stock_signals=stock_signals,
        )
        model = DuolingoDAUModel()
        X, y = model.prepare_features(dau_df, trend_signals, alt_signals, stock_signals)
        model.fit(X, y)
        output["dau_m"] = {"forward": fwd, "feature_importance": model.feature_importance()}

    return output
