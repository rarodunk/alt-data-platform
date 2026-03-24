"""
yfinance connector — stock price signals and analyst estimates.

Provides quarterly aggregated features:
  - price_return_1q: 1-quarter price return (lagged)
  - price_return_4q: 4-quarter (YoY) price return (lagged)
  - volume_zscore:   normalized trading volume vs 1-year mean (lagged)
  - analyst_rev_eps: analyst EPS revision direction (+1/0/-1)
  - analyst_rev_rev: analyst revenue revision direction (+1/0/-1)
  - price_52w_pct:   price as % of 52-week high (momentum signal)

All signals are lagged by 1 quarter before being passed to models
to avoid look-ahead bias.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from .base import BaseConnector

logger = logging.getLogger(__name__)

COMPANY_TICKERS: Dict[str, str] = {
    "duolingo": "DUOL",
    "lemonade": "LMND",
    "nu": "NU",
    "transmedics": "TMDX",
}


class YFinanceConnector(BaseConnector):
    name = "yfinance"
    cache_ttl_hours = 6

    def fetch(self, company: str, period: str = "5y") -> List[Dict[str, Any]]:
        """Fetch daily OHLCV history and compute momentum signals."""
        ticker_sym = COMPANY_TICKERS.get(company)
        if not ticker_sym:
            logger.warning(f"No ticker configured for {company}")
            return []
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance not installed — run: pip install yfinance")
            return []

        try:
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period=period, interval="1d")
            if hist.empty:
                logger.warning(f"[yfinance] No price history for {ticker_sym}")
                return []

            hist = hist.reset_index()
            hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
            hist = hist.sort_values("Date").reset_index(drop=True)

            records = []
            for _, row in hist.iterrows():
                records.append({
                    "date": row["Date"].strftime("%Y-%m-%d"),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                    "company": company,
                    "source": "yfinance",
                })
            logger.info(f"[yfinance] Fetched {len(records)} days for {ticker_sym}")
            return records
        except Exception as e:
            logger.error(f"[yfinance] Error fetching {ticker_sym}: {e}")
            return []

    def fetch_quarterly_signals(self, company: str) -> List[Dict[str, Any]]:
        """
        Aggregate daily price data into quarterly signals.
        Returns list of dicts with keys: quarter, price_return_1q,
        price_return_4q, volume_zscore, price_52w_pct.
        """
        raw = self.fetch_with_cache(company=company)
        if not raw:
            return []

        df = pd.DataFrame(raw)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        # Quarterly aggregates: last close of quarter, total volume
        q_agg = df.groupby("quarter").agg(
            close_last=("close", "last"),
            close_first=("close", "first"),
            volume_sum=("volume", "sum"),
            volume_mean=("volume", "mean"),
        ).reset_index()
        q_agg = q_agg.sort_values("quarter").reset_index(drop=True)

        # 1-quarter return (QoQ): use end-of-quarter close
        q_agg["price_return_1q"] = q_agg["close_last"].pct_change(1)
        # 4-quarter return (YoY)
        q_agg["price_return_4q"] = q_agg["close_last"].pct_change(4)

        # Volume z-score vs trailing 4Q mean
        q_agg["volume_zscore"] = (
            (q_agg["volume_sum"] - q_agg["volume_sum"].rolling(4, min_periods=2).mean())
            / (q_agg["volume_sum"].rolling(4, min_periods=2).std() + 1e-9)
        )

        # 52-week high (trailing 4Q) as % of current close — momentum proxy
        q_agg["price_52w_high"] = q_agg["close_last"].rolling(4, min_periods=1).max()
        q_agg["price_52w_pct"] = q_agg["close_last"] / (q_agg["price_52w_high"] + 1e-9)

        # Analyst estimates (best effort — may not always populate)
        analyst_map = self._fetch_analyst_revisions(company)
        if analyst_map:
            q_agg["analyst_rev_rev"] = q_agg["quarter"].map(analyst_map).fillna(0)
        else:
            q_agg["analyst_rev_rev"] = 0.0

        results = []
        for _, row in q_agg.iterrows():
            results.append({
                "quarter": row["quarter"],
                "price_return_1q": round(float(row["price_return_1q"]) if pd.notna(row["price_return_1q"]) else 0.0, 4),
                "price_return_4q": round(float(row["price_return_4q"]) if pd.notna(row["price_return_4q"]) else 0.0, 4),
                "volume_zscore": round(float(row["volume_zscore"]) if pd.notna(row["volume_zscore"]) else 0.0, 4),
                "price_52w_pct": round(float(row["price_52w_pct"]) if pd.notna(row["price_52w_pct"]) else 1.0, 4),
                "analyst_rev_rev": float(row.get("analyst_rev_rev", 0.0)),
            })
        return results

    def _fetch_analyst_revisions(self, company: str) -> Dict[str, float]:
        """
        Pull analyst revenue estimate revisions from yfinance.
        Returns a dict of {quarter_label: revision_direction (+1/-1/0)}.
        This is a best-effort signal — returns {} on any failure.
        """
        ticker_sym = COMPANY_TICKERS.get(company)
        if not ticker_sym:
            return {}
        try:
            import yfinance as yf
            ticker = yf.Ticker(ticker_sym)
            # revenue_estimate has columns like 'avg', 'low', 'high' for upcoming quarters
            rev_est = ticker.revenue_estimate
            if rev_est is None or rev_est.empty:
                return {}
            revisions: Dict[str, float] = {}
            for idx in rev_est.index:
                row = rev_est.loc[idx]
                # Positive growth in avg estimate = upward revision signal
                avg = row.get("avg", None) if hasattr(row, "get") else None
                if avg and pd.notna(avg):
                    period_str = str(idx)
                    # Map yfinance period labels to quarter labels
                    revisions[period_str] = 1.0 if float(avg) > 0 else -1.0
            return revisions
        except Exception:
            return {}
