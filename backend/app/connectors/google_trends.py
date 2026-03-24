import logging
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .base import BaseConnector

logger = logging.getLogger(__name__)

COMPANY_KEYWORDS: Dict[str, List[str]] = {
    "duolingo": ["duolingo", "learn language app", "duolingo plus"],
    "lemonade": ["lemonade insurance", "lemonade renters insurance"],
    "nu": ["nubank", "nu bank", "cartão nubank"],
    "transmedics": ["transmedics", "organ transplant", "organ care system"],
}


class GoogleTrendsConnector(BaseConnector):
    name = "google_trends"
    cache_ttl_hours = 12

    def fetch(self, company: str, timeframe: str = "today 5-y") -> List[Dict[str, Any]]:
        """Fetch Google Trends interest data for a company's keywords."""
        try:
            from pytrends.request import TrendReq
        except ImportError:
            logger.error("pytrends not installed")
            return []

        keywords = COMPANY_KEYWORDS.get(company, [])
        if not keywords:
            logger.warning(f"No keywords configured for {company}")
            return []

        results = []

        # pytrends supports up to 5 keywords per request
        for i in range(0, len(keywords), 5):
            batch = keywords[i : i + 5]
            for attempt in range(3):
                try:
                    pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
                    pytrends.build_payload(batch, cat=0, timeframe=timeframe, geo="", gprop="")
                    interest_df = pytrends.interest_over_time()

                    if interest_df.empty:
                        logger.warning(f"No trends data returned for {company} batch {batch}")
                        break

                    interest_df = interest_df.drop(columns=["isPartial"], errors="ignore")
                    interest_df = interest_df.reset_index()

                    for _, row in interest_df.iterrows():
                        date_str = str(row["date"])[:10]
                        for kw in batch:
                            if kw in row:
                                val = float(row[kw]) if row[kw] is not None else 0.0
                                results.append(
                                    {
                                        "date": date_str,
                                        "keyword": kw,
                                        "interest_value": val,
                                        "normalized_value": val / 100.0,
                                        "company": company,
                                        "source": "google_trends",
                                    }
                                )
                    break  # success

                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "Too Many Requests" in err_str:
                        wait = (2**attempt) * 10 + random.uniform(0, 5)
                        logger.warning(f"Rate limited by Google Trends. Waiting {wait:.1f}s (attempt {attempt + 1})")
                        time.sleep(wait)
                    elif "Timeout" in err_str:
                        wait = 5 + attempt * 3
                        logger.warning(f"Timeout fetching trends for {batch}. Waiting {wait}s")
                        time.sleep(wait)
                    else:
                        logger.error(f"Error fetching Google Trends for {batch}: {e}")
                        break

            # polite delay between batches
            if i + 5 < len(keywords):
                time.sleep(2 + random.uniform(0, 2))

        logger.info(f"[google_trends] Fetched {len(results)} data points for {company}")
        return results

    def fetch_quarterly_aggregates(self, company: str) -> List[Dict[str, Any]]:
        """Return quarterly averaged interest per keyword."""
        import pandas as pd

        raw = self.fetch_with_cache(company=company)
        if not raw:
            return []

        df = pd.DataFrame(raw)
        df["date"] = pd.to_datetime(df["date"])
        df["quarter"] = df["date"].dt.to_period("Q").astype(str)

        agg = (
            df.groupby(["quarter", "keyword"])["interest_value"]
            .mean()
            .reset_index()
            .rename(columns={"interest_value": "avg_interest"})
        )
        return agg.to_dict(orient="records")
