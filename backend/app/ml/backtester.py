"""
Walk-forward backtesting engine.
Train on [0..t], predict t+1. No look-ahead bias.
"""
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _compute_metrics(actuals: List[float], predictions: List[float]) -> Dict[str, float]:
    if len(actuals) < 2:
        return {}
    a = np.array(actuals)
    p = np.array(predictions)
    errors = a - p
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    mape = float(np.mean(np.abs(errors / (a + 1e-9))) * 100)

    # Directional accuracy: does direction of change match?
    if len(a) > 1:
        actual_dir = np.sign(np.diff(a))
        pred_dir = np.sign(np.diff(p))
        dir_acc = float(np.mean(actual_dir == pred_dir)) * 100
    else:
        dir_acc = 0.0

    return {
        "mae": round(mae, 4),
        "mape": round(mape, 4),
        "rmse": round(rmse, 4),
        "directional_accuracy": round(dir_acc, 2),
        "n_quarters": len(a),
    }


def run_backtest(
    actuals_df: pd.DataFrame,
    features_df: pd.DataFrame,
    target_col: str,
    model_factory,
    min_train_quarters: int = 6,
) -> Dict:
    """
    Walk-forward backtest.

    Parameters
    ----------
    actuals_df : pd.DataFrame
        Must contain 'quarter', 'period_end', and target_col columns, sorted ascending.
    features_df : pd.DataFrame
        Feature matrix aligned with actuals_df (same row count / index).
    target_col : str
    model_factory : callable
        Called each iteration to create a fresh model instance.
    min_train_quarters : int
        Minimum quarters needed before first prediction.

    Returns
    -------
    dict with keys 'results' (list of per-quarter dicts) and 'metrics' (aggregate stats).
    """
    n = len(actuals_df)
    if n < min_train_quarters + 1:
        logger.warning(f"Not enough data to backtest: {n} rows, need {min_train_quarters + 1}")
        return {"results": [], "metrics": {}}

    actuals_df = actuals_df.reset_index(drop=True)
    features_df = features_df.reset_index(drop=True)
    y = actuals_df[target_col].values

    results = []

    for t in range(min_train_quarters, n):
        X_train = features_df.iloc[:t]
        y_train = y[:t]
        X_pred = features_df.iloc[[t]]
        y_true = float(y[t])

        try:
            model = model_factory()
            model.fit(X_train, pd.Series(y_train))
            point, lower, upper = model.predict(X_pred)
        except Exception as e:
            logger.warning(f"Backtest step t={t} failed: {e}")
            continue

        error = y_true - point
        pct_error = (error / (y_true + 1e-9)) * 100

        results.append(
            {
                "quarter": actuals_df.iloc[t]["quarter"],
                "period_end": actuals_df.iloc[t]["period_end"],
                "actual_value": round(y_true, 4),
                "predicted_value": round(point, 4),
                "confidence_lower": round(lower, 4),
                "confidence_upper": round(upper, 4),
                "error": round(error, 4),
                "pct_error": round(pct_error, 4),
            }
        )

    metrics = _compute_metrics(
        [r["actual_value"] for r in results],
        [r["predicted_value"] for r in results],
    )

    return {"results": results, "metrics": metrics}
