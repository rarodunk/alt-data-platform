"""Nu Holdings model — target: customers_m."""
import logging
from typing import Dict, Optional, Tuple
import pandas as pd
from .base_model import BaseForecaster
from .feature_engineering import build_features
from .backtester import run_backtest
from .forecast_utils import multi_quarter_forecast

logger = logging.getLogger(__name__)


class NuCustomerModel(BaseForecaster):
    def __init__(self):
        super().__init__(target_col="customers_m", min_train_quarters=5)

    def prepare_features(self, actuals_df: pd.DataFrame,
                         trend_signals: Optional[pd.DataFrame] = None,
                         alt_signals: Optional[pd.DataFrame] = None,
                         stock_signals: Optional[pd.DataFrame] = None, **_) -> Tuple[pd.DataFrame, pd.Series]:
        df = actuals_df[actuals_df["customers_m"].notna()].copy()
        X = build_features(df, "customers_m", trend_signals=trend_signals,
                           alt_signals=alt_signals, stock_signals=stock_signals)
        y = df["customers_m"].reset_index(drop=True)
        return X, y


def run_nu_backtest(actuals_df: pd.DataFrame,
                    trend_signals: Optional[pd.DataFrame] = None,
                    alt_signals: Optional[pd.DataFrame] = None,
                    stock_signals: Optional[pd.DataFrame] = None) -> Dict:
    df = actuals_df[actuals_df["customers_m"].notna()].copy().reset_index(drop=True)
    if len(df) < 6:
        return {"customers_m": {"results": [], "metrics": {}}}
    tmp = NuCustomerModel()
    X, _ = tmp.prepare_features(df, trend_signals, alt_signals, stock_signals)
    return {"customers_m": run_backtest(df, X, "customers_m",
                                        model_factory=NuCustomerModel, min_train_quarters=5)}


def get_nu_forecast(actuals_df: pd.DataFrame,
                    trend_signals: Optional[pd.DataFrame] = None,
                    alt_signals: Optional[pd.DataFrame] = None,
                    stock_signals: Optional[pd.DataFrame] = None,
                    horizons: int = 4) -> Dict:
    df = actuals_df[actuals_df["customers_m"].notna()].copy().reset_index(drop=True)
    if len(df) < 5:
        return {}
    fwd = multi_quarter_forecast(NuCustomerModel, df, "customers_m",
                                 horizons=horizons, trend_signals=trend_signals,
                                 alt_signals=alt_signals, stock_signals=stock_signals)
    model = NuCustomerModel()
    X, y = model.prepare_features(df, trend_signals, alt_signals, stock_signals)
    model.fit(X, y)
    return {"customers_m": {"forward": fwd, "feature_importance": model.feature_importance()}}
