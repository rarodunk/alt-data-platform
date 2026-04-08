"""
Chess Tracker API Routes — Duolingo Chess vs Chess.com
Compares web visit proxies (Google Trends) and download proxies (App Store ratings).
"""
import logging
from fastapi import APIRouter

from ...connectors.chess_tracker_connector import ChessTrackerConnector

logger = logging.getLogger(__name__)

router = APIRouter()
_connector = ChessTrackerConnector()


@router.get("/chess-tracker/trends")
def get_trends():
    """
    Google Trends comparison: chess.com vs duolingo chess.
    Interest index 0–100; higher = more relative search volume. Used as a web visits proxy.
    """
    data = _connector.fetch_with_cache()
    chess_com = [d for d in data if d.get("keyword") == "chess.com"]
    duolingo_chess = [d for d in data if d.get("keyword") == "duolingo chess"]
    return {
        "chess_com": chess_com,
        "duolingo_chess": duolingo_chess,
        "source": "google_trends",
        "note": "Interest index 0–100. Relative search volume — a proxy for web visit share.",
    }


@router.get("/chess-tracker/appstore")
def get_appstore():
    """
    App Store rating counts (download proxy) — historical weekly + live snapshot.
    Rating count is strongly correlated with cumulative downloads.
    """
    historical = _connector.get_appstore_historical()
    live = _connector.fetch_appstore_current()
    return {
        "historical": historical,
        "live": live,
        "source": "itunes_api + curated_milestones",
        "note": "Rating count is a strong proxy for cumulative app downloads.",
    }


@router.get("/chess-tracker/summary")
def get_summary():
    """Latest snapshot KPIs: current search interest and live App Store ratings."""
    trends_data = _connector.fetch_with_cache()

    # Most recent week's interest values
    latest_date = max((d["date"] for d in trends_data), default=None)
    if latest_date:
        latest_rows = [d for d in trends_data if d["date"] == latest_date]
        chess_com_latest = next(
            (d["interest_value"] for d in latest_rows if d.get("keyword") == "chess.com"), None
        )
        duolingo_chess_latest = next(
            (d["interest_value"] for d in latest_rows if d.get("keyword") == "duolingo chess"), None
        )
    else:
        chess_com_latest = duolingo_chess_latest = None

    # Peak interest over full window
    chess_com_peak = max(
        (d["interest_value"] for d in trends_data if d.get("keyword") == "chess.com"), default=None
    )
    duolingo_chess_peak = max(
        (d["interest_value"] for d in trends_data if d.get("keyword") == "duolingo chess"), default=None
    )

    live = _connector.fetch_appstore_current()
    chess_com_app = next((d for d in live if d.get("app") == "chess_com"), None)
    duolingo_app = next((d for d in live if d.get("app") == "duolingo"), None)

    return {
        "as_of": latest_date,
        "trends": {
            "chess_com": {
                "latest_interest": chess_com_latest,
                "peak_interest": chess_com_peak,
            },
            "duolingo_chess": {
                "latest_interest": duolingo_chess_latest,
                "peak_interest": duolingo_chess_peak,
            },
        },
        "appstore": {
            "chess_com": chess_com_app,
            "duolingo": duolingo_app,
        },
    }
