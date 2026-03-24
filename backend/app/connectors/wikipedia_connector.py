"""
Wikipedia pageviews connector — free Wikimedia REST API.
Weekly page view counts are a strong brand-awareness proxy.
"""
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .base import BaseConnector

logger = logging.getLogger(__name__)

COMPANY_ARTICLES = {
    "duolingo": "Duolingo",
    "lemonade": "Lemonade_(insurance_company)",
    "nu": "Nu_Holdings",
    "transmedics": "TransMedics",
}


class WikipediaConnector(BaseConnector):
    name = "wikipedia"
    cache_ttl_hours = 48

    def fetch(self, company: str, years_back: int = 5) -> List[Dict[str, Any]]:
        article = COMPANY_ARTICLES.get(company)
        if not article:
            logger.warning(f"[wikipedia] No article configured for {company}")
            return []

        end = datetime.utcnow()
        start = end - timedelta(days=365 * years_back)
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        url = (
            f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
            f"/en.wikipedia/all-access/all-agents/{article}/monthly/{start_str}/{end_str}"
        )

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "altdata-platform/1.0 (research tool)"},
                timeout=15,
            )
            if resp.status_code == 404:
                logger.warning(f"[wikipedia] Article not found: {article}")
                return []
            resp.raise_for_status()
            items = resp.json().get("items", [])

            results = []
            for item in items:
                ts = item["timestamp"]  # e.g. "2021010100"
                date_str = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
                views = float(item.get("views", 0))
                results.append({
                    "date": date_str,
                    "pageviews": views,
                    "company": company,
                    "source": "wikipedia",
                })

            logger.info(f"[wikipedia] Fetched {len(results)} weekly records for {company}")
            return results

        except Exception as e:
            logger.error(f"[wikipedia] Error fetching {company}: {e}")
            return []
