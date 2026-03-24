"""Lemonade model — target: customers_k."""
import logging
from typing import Dict, Optional, Tuple
import pandas as pd
from .base_model import BaseForecaster
from .feature_engineering import build_features
from .backtester import run_backtest
from .forecast_utils import multi_quarter_forecast

logger = logging.getLogger(__name__)


class LemonadeCustomerModel(BaseForecaster):
    def __init__(self):
        super().__init__(target_col="customers_k", min_train_quarters=6)

    def prepare_features(self, actuals_df: pd.DataFrame,
                         trend_signals: Optional[pd.DataFrame] = None,
                         alt_signals: Optional[pd.DataFrame] = None,
                         stock_signals: Optional[pd.DataFrame] = None, **_) -> Tuple[pd.DataFrame, pd.Series]:
        df = actuals_df[actuals_df["customers_k"].notna()].copy()
        X = build_features(df, "customers_k", trend_signals=trend_signals,
                           alt_signals=alt_signals, stock_signals=stock_signals)
        y = df["customers_k"].reset_index(drop=True)
        return X, y


def run_lemonade_backtest(actuals_df: pd.DataFrame,
                          trend_signals: Optional[pd.DataFrame] = None,
                          alt_signals: Optional[pd.DataFrame] = None,
                          stock_signals: Optional[pd.DataFrame] = None) -> Dict:
    df = actuals_df[actuals_df["customers_k"].notna()].copy().reset_index(drop=True)
    if len(df) < 7:
        return {"customers_k": {"results": [], "metrics": {}}}
    tmp = LemonadeCustomerModel()
    X, _ = tmp.prepare_features(df, trend_signals, alt_signals, stock_signals)
    return {"customers_k": run_backtest(df, X, "customers_k",
                                        model_factory=LemonadeCustomerModel, min_train_quarters=6)}


def get_lemonade_forecast(actuals_df: pd.DataFrame,
                          trend_signals: Optional[pd.DataFrame] = None,
                          alt_signals: Optional[pd.DataFrame] = None,
                          stock_signals: Optional[pd.DataFrame] = None,
                          horizons: int = 4) -> Dict:
    df = actuals_df[actuals_df["customers_k"].notna()].copy().reset_index(drop=True)
    if len(df) < 6:
        return {}
    fwd = multi_quarter_forecast(LemonadeCustomerModel, df, "customers_k",
                                 horizons=horizons, trend_signals=trend_signals,
                                 alt_signals=alt_signals, stock_signals=stock_signals)
    model = LemonadeCustomerModel()
    X, y = model.prepare_features(df, trend_signals, alt_signals, stock_signals)
    model.fit(X, y)
    return {"customers_k": {"forward": fwd, "feature_importance": model.feature_importance()}}
