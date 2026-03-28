"""
SEC EDGAR connector — pulls quarterly revenue actuals from XBRL filings.

Uses the free, no-auth SEC EDGAR data APIs:
  https://data.sec.gov/api/xbrl/companyfacts/{CIK}.json

Covers revenue for DUOL, LMND, NU, TMDX. Operational metrics
(DAU, customer count) are not consistently XBRL-tagged, so those
continue to come from seed files.
"""
import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# SEC EDGAR CIKs — zero-padded to 10 digits
COMPANY_CIKS: Dict[str, str] = {
    "duolingo":    "0001819989",
    "lemonade":    "0001730469",
    "nu":          "0001852536",
    "transmedics": "0001670076",
}

# XBRL concepts to try in order for each company
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
]

EDGAR_HEADERS = {
    "User-Agent": "altdata-platform research@example.com",
    "Accept-Encoding": "gzip, deflate",
}


def _lookup_cik(ticker: str) -> Optional[str]:
    """Look up CIK from SEC's company_tickers.json (fallback if hardcode is stale)."""
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception as e:
        logger.warning(f"[edgar] CIK lookup failed for {ticker}: {e}")
    return None


def fetch_company_facts(cik: str) -> Optional[Dict]:
    """Fetch the full XBRL company facts JSON from SEC EDGAR."""
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=EDGAR_HEADERS, timeout=30)
        if resp.status_code == 404:
            logger.warning(f"[edgar] No XBRL data found for CIK {cik}")
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[edgar] Error fetching company facts for CIK {cik}: {e}")
        return None


def _extract_quarterly_revenue(facts: Dict, company: str) -> List[Dict[str, Any]]:
    """
    Extract quarterly (10-Q / 10-K) revenue figures from XBRL facts.
    Returns list of dicts: {quarter, period_end, revenue_m, source}.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    if not us_gaap:
        logger.warning(f"[edgar] No us-gaap facts found for {company}")
        return []

    concept_data = None
    used_concept = None
    for concept in REVENUE_CONCEPTS:
        if concept in us_gaap:
            concept_data = us_gaap[concept]
            used_concept = concept
            break

    if not concept_data:
        logger.warning(f"[edgar] No revenue concept found for {company}. Available: {list(us_gaap.keys())[:10]}")
        return []

    # Find USD units
    units = concept_data.get("units", {})
    usd_data = units.get("USD", [])
    if not usd_data:
        logger.warning(f"[edgar] No USD units for {used_concept} in {company}")
        return []

    results = []
    seen_quarters = set()

    for entry in usd_data:
        form = entry.get("form", "")
        # Only use 10-Q (quarterly) and 10-K (annual) filings
        if form not in ("10-Q", "10-K", "20-F"):
            continue
        # Only instant or duration periods that are ~1 quarter long
        start = entry.get("start")
        end = entry.get("end")
        if not end:
            continue

        # For 10-Q, the period should be ~90 days; for 10-K we skip (it's annual)
        if start and end:
            from datetime import date
            try:
                d_start = date.fromisoformat(start)
                d_end = date.fromisoformat(end)
                days = (d_end - d_start).days
                # Quarterly = 80–100 days; skip annual or other
                if days < 60 or days > 110:
                    continue
            except Exception:
                continue

        val = entry.get("val")
        if val is None:
            continue

        import pandas as pd
        period = pd.Period(end, freq="Q")
        quarter_label = f"Q{period.quarter} {period.year}"

        revenue_m = round(float(val) / 1_000_000, 4)
        # Keep the maximum value for each quarter (total revenue > segment revenue)
        if quarter_label in seen_quarters:
            for r in results:
                if r["quarter"] == quarter_label and revenue_m > r["revenue_m"]:
                    r["revenue_m"] = revenue_m
                    r["source"] = f"edgar_{used_concept}"
            continue
        seen_quarters.add(quarter_label)

        results.append({
            "quarter": quarter_label,
            "period_end": end,
            "revenue_m": revenue_m,
            "source": f"edgar_{used_concept}",
        })

    results.sort(key=lambda x: x["period_end"])
    logger.info(f"[edgar] Extracted {len(results)} quarterly revenue records for {company}")
    return results


class SECEdgarConnector:
    """Fetch and parse quarterly revenue actuals from SEC EDGAR."""

    def get_revenue_actuals(self, company: str) -> List[Dict[str, Any]]:
        """
        Return quarterly revenue in millions for a company.
        Returns [] if company not supported or EDGAR data unavailable.
        """
        cik = COMPANY_CIKS.get(company)
        if not cik:
            logger.warning(f"[edgar] No CIK configured for {company}")
            return []

        facts = fetch_company_facts(cik)
        if not facts:
            # Fallback: try dynamic lookup
            ticker_map = {"duolingo": "DUOL", "lemonade": "LMND", "nu": "NU", "transmedics": "TMDX"}
            ticker = ticker_map.get(company)
            if ticker:
                cik = _lookup_cik(ticker)
                if cik:
                    facts = fetch_company_facts(cik)

        if not facts:
            return []

        time.sleep(0.1)  # respect SEC rate limits
        return _extract_quarterly_revenue(facts, company)

    def get_all_companies(self, companies: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """Fetch revenue actuals for multiple companies."""
        if companies is None:
            companies = list(COMPANY_CIKS.keys())
        results = {}
        for co in companies:
            results[co] = self.get_revenue_actuals(co)
            time.sleep(0.2)
        return results
