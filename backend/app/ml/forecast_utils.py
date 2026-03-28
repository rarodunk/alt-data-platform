"""
Multi-quarter iterative forward forecasting utilities.
Trains on all known data, then iterates: predict Q+1, append as pseudo-actual,
predict Q+2, etc.  Confidence intervals widen with each horizon step.
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

    Returns list of dicts:
      {quarter, period_end, predicted_value, confidence_lower, confidence_upper,
       horizon (1=next, 2=one after, ...), note}
    """
    # --- estimate base residual std from in-sample fit ---
    working_df = actuals_df[actuals_df[target_col].notna()].copy().reset_index(drop=True)
    if len(working_df) < 4:
        return []

    model0 = model_class()
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

    # Fit on all known data
    try:
        if kwargs:
            X0, y0 = model0.prepare_features(working_df, **kwargs)
        else:
            X0, y0 = model0.prepare_features(working_df)
        model0.fit(X0, y0)
        in_sample_preds = [float(model0.predict(X0.iloc[[i]])[0]) for i in range(len(X0))]
        residuals = np.abs(np.array(y0) - np.array(in_sample_preds))
        base_std = float(np.std(residuals)) if len(residuals) > 1 else float(np.mean(np.abs(np.array(y0) * 0.05)))
    except Exception as e:
        logger.warning(f"Could not compute base_std: {e}")
        base_std = float(working_df[target_col].mean() * 0.05)

    # Compute naive growth anchor from recent deltas
    known_y = working_df[target_col].dropna()
    recent_deltas = known_y.diff().dropna().tail(4)
    avg_delta = float(recent_deltas.mean()) if len(recent_deltas) > 0 else 0.0
    # A series is "consistently growing" if all last 4 deltas are positive
    is_monotone_growth = (len(recent_deltas) >= 3 and (recent_deltas > 0).all())

    results = []
    df_rolling = working_df.copy()

    for h in range(1, horizons + 1):
        try:
            # Retrain on all data available at this horizon
            model_h = model_class()
            if kwargs:
                Xh, yh = model_h.prepare_features(df_rolling, **kwargs)
            else:
                Xh, yh = model_h.prepare_features(df_rolling)
            model_h.fit(Xh, yh)

            # Build next row and predict
            next_row = build_next_row(df_rolling, target_col)
            extended = pd.concat([df_rolling, next_row], ignore_index=True)
            if kwargs:
                X_ext, _ = model_h.prepare_features(extended, **kwargs)
            else:
                X_ext, _ = model_h.prepare_features(extended)

            point, lower_base, upper_base = model_h.predict(X_ext.iloc[[-1]])

            # --- Growth floor ---
            # For consistently-growing series, the naive anchor is a hard floor.
            # This prevents the model from predicting a decline when every recent
            # quarter has been positive growth.
            last_known = float(df_rolling[target_col].dropna().iloc[-1])
            if is_monotone_growth and avg_delta > 0:
                # Floor 1: sequential — last + 50% of 4Q avg delta
                seq_floor = last_known + avg_delta * 0.50
                min_pred = seq_floor

                # Floor 2: YoY continuation — same quarter last year × (1 + recent_yoy × 0.70)
                # Captures seasonal patterns and YoY momentum that sequential delta misses.
                # Uses proper same-quarter YoY (iloc[-4] vs iloc[-8]) to preserve seasonality:
                # e.g. Q4 with historically strong Q3→Q4 lift will floor at a higher level.
                # 0.70 allows meaningful deceleration (e.g. 30% YoY → floor at ~21% YoY).
                known_series = df_rolling[target_col].dropna()
                if len(known_series) >= 5:
                    same_q_last_yr = float(known_series.iloc[-4])
                    # Use same quarter 2 years ago if available for a true YoY rate
                    if len(known_series) >= 8:
                        same_q_2_yrs_ago = float(known_series.iloc[-8])
                    else:
                        same_q_2_yrs_ago = float(known_series.iloc[-5])
                    recent_yoy = (same_q_last_yr - same_q_2_yrs_ago) / (same_q_2_yrs_ago + 1e-9)
                    if recent_yoy > 0:
                        # Use a sliding decay: higher YoY gets a lower multiplier.
                        # 20% YoY → 0.75 multiplier (floor at 15%), preserves momentum
                        # 40% YoY → 0.60 multiplier (floor at 24%), moderate deceleration
                        # 60% YoY → 0.50 multiplier (floor at 30%), strong deceleration
                        decay = max(0.45, 0.80 - recent_yoy * 0.50)
                        yoy_floor = same_q_last_yr * (1 + recent_yoy * decay)
                        min_pred = max(min_pred, yoy_floor)

                if point < min_pred:
                    logger.debug(
                        f"Growth floor applied at h={h}: model={point:.2f} → floor={min_pred:.2f}"
                    )
                    point = min_pred

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

            # Append prediction as pseudo-actual for next iteration
            imputed_row = build_next_row(df_rolling, target_col, imputed_value=point)
            df_rolling = pd.concat([df_rolling, imputed_row], ignore_index=True)

        except Exception as e:
            logger.error(f"Error forecasting horizon {h}: {e}")
            break

    return results
