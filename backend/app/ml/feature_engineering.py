"""
Feature engineering pipeline.
All operations respect temporal ordering — no look-ahead bias.
"""
import logging
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_features(
    actuals_df: pd.DataFrame,
    target_col: str,
    trend_signals: Optional[pd.DataFrame] = None,
    flight_signals: Optional[pd.DataFrame] = None,
    alt_signals: Optional[pd.DataFrame] = None,
    stock_signals: Optional[pd.DataFrame] = None,
    structural_break_quarter: Optional[str] = None,
    seasonal_dummies: bool = True,
) -> pd.DataFrame:
    """
    Build a feature matrix from a time-ordered actuals DataFrame.

    Parameters
    ----------
    actuals_df : pd.DataFrame
        Columns: quarter, period_end, <target_col>. Must be sorted ascending.
    target_col : str
        Column to predict.
    trend_signals : pd.DataFrame, optional
        Columns: quarter, keyword, avg_interest — from Google Trends quarterly aggregates.
    flight_signals : pd.DataFrame, optional
        Columns: quarter, total_flights, avg_utilization, etc.
    alt_signals : pd.DataFrame, optional
        Wide DataFrame with columns: quarter, <feature_name>, ... — e.g. reddit_post_count,
        appstore_avg_rating. Each column is merged by quarter and lagged by 1Q to avoid
        look-ahead bias.
    structural_break_quarter : str, optional
        Quarter where a structural break occurs (e.g. "2023Q1"). Adds a dummy variable.

    Returns
    -------
    pd.DataFrame with features. Index is the same as actuals_df.
    """
    df = actuals_df.copy().reset_index(drop=True)
    df = df.sort_values("period_end").reset_index(drop=True)

    y = df[target_col].copy()

    features = pd.DataFrame(index=df.index)
    features["period_end"] = pd.to_datetime(df["period_end"])

    # --- Lag features ---
    for lag in [1, 2, 3, 4]:
        features[f"{target_col}_lag{lag}"] = y.shift(lag)

    # --- Rolling statistics (use .shift(1) to avoid look-ahead) ---
    features[f"{target_col}_roll2"] = y.shift(1).rolling(2, min_periods=1).mean()
    features[f"{target_col}_roll4"] = y.shift(1).rolling(4, min_periods=1).mean()

    # --- Absolute QoQ delta features ---
    # These capture the raw growth per quarter — essential for growth series.
    # Without these, lag+rolling-mean models revert toward historical averages
    # instead of extrapolating the current growth trajectory.
    delta = y.diff(1)
    features[f"{target_col}_delta1"]    = delta.shift(1)                          # last QoQ absolute change
    features[f"{target_col}_delta_ma2"] = delta.shift(1).rolling(2, min_periods=1).mean()
    features[f"{target_col}_delta_ma4"] = delta.shift(1).rolling(4, min_periods=1).mean()
    features[f"{target_col}_delta_accel"] = delta.diff(1).shift(1)                 # is growth speeding up?

    # --- Naive growth anchor: lag1 + recent average delta ---
    # This directly encodes "continue growing at recent rate".
    # Giving this to Ridge/XGBoost as a feature lets models learn a coefficient
    # near 1 on it, producing trend-following forecasts without look-ahead bias.
    features[f"{target_col}_naive_growth"] = (
        y.shift(1) + delta.shift(1).rolling(4, min_periods=1).mean()
    )

    # --- Percentage growth rates ---
    features[f"{target_col}_qoq"] = y.shift(1).pct_change(1)
    features[f"{target_col}_yoy"] = y.shift(4).pct_change(1)  # vs same Q last year

    # --- YoY continuation anchor ---
    # "If the most recently observable YoY growth rate continues, what is the forecast?"
    # Uses shift(1)/shift(5) to avoid look-ahead; for prediction row this translates to:
    #   same_q_last_year * (1 + last_reported_yoy_rate)
    # Gives model a direct signal toward trend continuation vs mean reversion.
    recent_yoy_rate = (y.shift(1) - y.shift(5)) / (y.shift(5) + 1e-9)
    features[f"{target_col}_yoy_continuation"] = y.shift(4) * (1 + recent_yoy_rate)

    # --- Linear trend extrapolation (rolling OLS on last 8Q, no look-ahead) ---
    trend_extrap = np.full(len(df), np.nan)
    for i in range(len(df)):
        window_y = y.iloc[max(0, i - 7):i].dropna()
        if len(window_y) >= 3:
            x = np.arange(len(window_y), dtype=float)
            try:
                slope, intercept = np.polyfit(x, window_y.values, 1)
                trend_extrap[i] = intercept + slope * len(window_y)
            except Exception:
                pass
    features[f"{target_col}_trend_extrap"] = trend_extrap

    # --- Linear trend index ---
    features["trend_idx"] = np.arange(len(df))

    # --- Quarter-of-year seasonality dummies ---
    if seasonal_dummies:
        features["period_end"] = pd.to_datetime(df["period_end"])
        quarter_num = features["period_end"].dt.quarter
        for q in [1, 2, 3, 4]:
            features[f"is_q{q}"] = (quarter_num == q).astype(int)

    # --- Structural break dummy ---
    if structural_break_quarter:
        # Normalise: "Q1 2023" -> "2023Q1" and compare with period label
        df["_period_label"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
        break_norm = structural_break_quarter.replace(" ", "").upper()
        features["post_break"] = (
            df["_period_label"].apply(
                lambda x: 1 if x.replace(" ", "").upper() >= break_norm else 0
            )
        )

    # --- Google Trends signals ---
    if trend_signals is not None and not trend_signals.empty:
        try:
            # Pivot: one column per keyword, indexed by quarter
            pivot = trend_signals.pivot_table(
                index="quarter", columns="keyword", values="avg_interest", aggfunc="mean"
            )
            pivot.columns = [f"trend_{c.replace(' ', '_')}" for c in pivot.columns]
            pivot = pivot.reset_index()

            df["_quarter_label"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
            merged = df[["_quarter_label"]].merge(pivot, left_on="_quarter_label", right_on="quarter", how="left")
            trend_cols = [c for c in merged.columns if c.startswith("trend_")]
            for col in trend_cols:
                features[col] = merged[col].values
                # Lagged trend (signal from prior quarter to avoid look-ahead)
                features[f"{col}_lag1"] = merged[col].shift(1).values
        except Exception as e:
            logger.warning(f"Could not merge trend signals: {e}")

    # --- Flight signals (TransMedics) ---
    if flight_signals is not None and not flight_signals.empty:
        try:
            fs = flight_signals.copy()
            fs.columns = [f"flight_{c}" if c != "quarter" else c for c in fs.columns]
            df["_quarter_label"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
            merged_f = df[["_quarter_label"]].merge(fs, left_on="_quarter_label", right_on="quarter", how="left")
            flight_cols = [c for c in merged_f.columns if c.startswith("flight_")]
            for col in flight_cols:
                features[col] = merged_f[col].values
        except Exception as e:
            logger.warning(f"Could not merge flight signals: {e}")

    # --- Generic alt signals (Reddit, App Store, etc.) ---
    if alt_signals is not None and not alt_signals.empty:
        try:
            df["_quarter_label"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
            merged_a = df[["_quarter_label"]].merge(
                alt_signals, left_on="_quarter_label", right_on="quarter", how="left"
            )
            alt_cols = [c for c in merged_a.columns if c not in ("quarter", "_quarter_label")]
            for col in alt_cols:
                # Lag by 1Q to avoid look-ahead: signal from prior quarter predicts this one
                features[col] = merged_a[col].shift(1).values
        except Exception as e:
            logger.warning(f"Could not merge alt signals: {e}")

    # --- Stock price signals (yfinance) ---
    # Lagged 1Q: last quarter's price momentum predicts this quarter's fundamentals.
    if stock_signals is not None and not stock_signals.empty:
        try:
            df["_quarter_label"] = pd.to_datetime(df["period_end"]).dt.to_period("Q").astype(str)
            stock_cols = [c for c in stock_signals.columns if c != "quarter"]
            merged_s = df[["_quarter_label"]].merge(
                stock_signals, left_on="_quarter_label", right_on="quarter", how="left"
            )
            for col in stock_cols:
                if col in merged_s.columns:
                    # Lag by 1Q — prior-quarter price signal predicts this quarter
                    features[f"stock_{col}"] = merged_s[col].shift(1).values
        except Exception as e:
            logger.warning(f"Could not merge stock signals: {e}")

    # --- Drop date helper columns ---
    features = features.drop(columns=["period_end"], errors="ignore")

    # --- Fill NaN: forward fill first, then zero ---
    features = features.ffill().fillna(0.0)

    # Replace infinities
    features = features.replace([np.inf, -np.inf], 0.0)

    return features
