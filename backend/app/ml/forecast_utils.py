"""
Multi-quarter iterative forward forecasting utilities.
Trains once on all known actuals, then iterates: predict Q+1, append as
pseudo-actual (for lag feature computation only), predict Q+2, etc.
The model is NOT retrained on pseudo-actuals — only real data trains it.
Confidence intervals widen with each horizon step.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional, Tuple
from dateutil.relativedelta import relativedelta
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _next_quarter(period_end: str) -> Tuple[str, str]:
    """Return (quarter_label, period_end_str) for the quarter after period_end."""
    dt = pd.to_datetime(period_end) + relativedelta(months=3)
    q = (dt.month - 1) // 3 + 1
    return f"Q{q} {dt.year}", dt.strftime("%Y-%m-%d")


def build_next_row(df: pd.DataFrame, target_col: str, imputed_value: Optional[float] = None) -> pd.DataFrame:
    """Append a synthetic row for the next quarter."""
    last = df.iloc[-1]
    next_label, next_end = _next_quarter(str(last["period_end"]))
    row = {c: None for c in df.columns}
    row["quarter"] = next_label
    row["period_end"] = next_end
    row[target_col] = imputed_value if imputed_value is not None else float("nan")
    return pd.DataFrame([row])


def multi_quarter_forecast(
    model_class,
    actuals_df: pd.DataFrame,
    target_col: str,
    horizons: int = 4,
    trend_signals: Optional[pd.DataFrame] = None,
    flight_signals: Optional[pd.DataFrame] = None,
    alt_signals: Optional[pd.DataFrame] = None,
    stock_signals: Optional[pd.DataFrame] = None,
    structural_break_quarter: Optional[str] = None,
) -> List[Dict]:
    """
    Iteratively forecast `horizons` quarters into the future.

    Train ONCE on all known actuals, then for each horizon build features
    using prior predictions as pseudo-actuals (for lag computation) but
    never retrain on them.  This prevents the model from learning its own
    conservative predictions and flattening the forecast.

    Returns list of dicts:
      {quarter, period_end, predicted_value, confidence_lower, confidence_upper,
       horizon (1=next, 2=one after, ...)}
    """
    working_df = actuals_df[actuals_df[target_col].notna()].copy().reset_index(drop=True)
    if len(working_df) < 4:
        return []

    kwargs = {}
    if trend_signals is not None:
        kwargs["trend_signals"] = trend_signals
    if flight_signals is not None:
        kwargs["flight_signals"] = flight_signals
    if alt_signals is not None:
        kwargs["alt_signals"] = alt_signals
    if stock_signals is not None:
        kwargs["stock_signals"] = stock_signals
    if structural_break_quarter is not None:
        kwargs["structural_break_quarter"] = structural_break_quarter

    # --- Train once on all known actuals ---
    model = model_class()
    try:
        if kwargs:
            X0, y0 = model.prepare_features(working_df, **kwargs)
        else:
            X0, y0 = model.prepare_features(working_df)
        model.fit(X0, y0)
        in_sample_preds = [float(model.predict(X0.iloc[[i]])[0]) for i in range(len(X0))]
        residuals = np.abs(np.array(y0) - np.array(in_sample_preds))
        base_std = float(np.std(residuals)) if len(residuals) > 1 else float(np.mean(np.abs(np.array(y0) * 0.05)))
    except Exception as e:
        logger.warning(f"Could not fit model: {e}")
        return []

    results = []
    df_rolling = working_df.copy()

    for h in range(1, horizons + 1):
        try:
            # Build next row and compute features using the SAME model (no retraining)
            next_row = build_next_row(df_rolling, target_col)
            extended = pd.concat([df_rolling, next_row], ignore_index=True)
            if kwargs:
                X_ext, _ = model.prepare_features(extended, **kwargs)
            else:
                X_ext, _ = model.prepare_features(extended)

            point, lower_base, upper_base = model.predict(X_ext.iloc[[-1]])

            # Only prevent obviously impossible predictions (negative values)
            point = max(point, 0)

            # Widen CI with horizon: scale factor grows as sqrt(h)
            ci_scale = np.sqrt(h) * 1.5
            ci_half = max(base_std * ci_scale, abs(upper_base - lower_base) / 2)
            lower = round(max(0, point - ci_half), 4)
            upper = round(point + ci_half, 4)

            next_label, next_end = _next_quarter(str(df_rolling.iloc[-1]["period_end"]))
            results.append({
                "quarter": next_label,
                "period_end": next_end,
                "predicted_value": round(point, 4),
                "confidence_lower": lower,
                "confidence_upper": upper,
                "horizon": h,
            })

            # Append prediction as pseudo-actual for FEATURE computation only
            # (the model is NOT retrained on this)
            imputed_row = build_next_row(df_rolling, target_col, imputed_value=point)
            df_rolling = pd.concat([df_rolling, imputed_row], ignore_index=True)

        except Exception as e:
            logger.error(f"Error forecasting horizon {h}: {e}")
            break

    return results
