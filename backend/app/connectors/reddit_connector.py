import logging
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .base import BaseConnector
from ..config import settings

logger = logging.getLogger(__name__)

COMPANY_SUBREDDITS: Dict[str, List[str]] = {
    "duolingo": ["duolingo", "languagelearning"],
    "lemonade": ["lemonade", "Insurance", "personalfinance"],
    "nu": ["nubank", "brdev", "financaspessoais"],
    "transmedics": ["medicine", "transplant"],
}

POSITIVE_WORDS = {
    "great", "amazing", "love", "excellent", "good", "awesome", "best", "perfect",
    "fantastic", "wonderful", "happy", "recommend", "helpful", "easy", "fast",
    "ótimo", "excelente", "bom", "adorei", "perfeito",
}
NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "horrible", "hate", "worst", "slow", "broken",
    "fraud", "scam", "cancel", "refund", "problem", "issue", "fail", "error",
    "ruim", "péssimo", "horrível", "cancelei",
}


def _simple_sentiment(text: str) -> float:
    """Return sentiment score in [-1, 1] using word matching."""
    if not text:
        return 0.0
    words = text.lower().split()
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


class RedditConnector(BaseConnector):
    name = "reddit"
    cache_ttl_hours = 6

    def _get_client(self):
        if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
            return None
        try:
            import praw

            reddit = praw.Reddit(
                client_id=settings.REDDIT_CLIENT_ID,
                client_secret=settings.REDDIT_CLIENT_SECRET,
                user_agent=settings.REDDIT_USER_AGENT,
            )
            return reddit
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            return None

    def fetch(self, company: str, weeks_back: int = 52) -> List[Dict[str, Any]]:
        """Fetch weekly Reddit activity for a company's subreddits."""
        reddit = self._get_client()
        if reddit is None:
            logger.info(f"[reddit] No credentials for {company} — using public JSON API")
            return self._fetch_public(company)

        subreddits = COMPANY_SUBREDDITS.get(company, [])
        results = []

        for sub_name in subreddits:
            try:
                sub = reddit.subreddit(sub_name)
                # Fetch recent hot posts as a proxy for weekly activity
                posts = list(sub.hot(limit=100))

                weekly_buckets: Dict[str, Dict] = {}
                for post in posts:
                    post_date = datetime.utcfromtimestamp(post.created_utc)
                    week_start = (post_date - timedelta(days=post_date.weekday())).strftime("%Y-%m-%d")

                    if week_start not in weekly_buckets:
                        weekly_buckets[week_start] = {
                            "post_count": 0,
                            "comment_count": 0,
                            "sentiment_scores": [],
                            "mention_count": 0,
                        }

                    bucket = weekly_buckets[week_start]
                    bucket["post_count"] += 1
                    bucket["comment_count"] += post.num_comments

                    title_lower = post.title.lower()
                    company_name = company.replace("_", " ")
                    if company_name in title_lower or company in title_lower:
                        bucket["mention_count"] += 1

                    sentiment = _simple_sentiment(post.title + " " + (post.selftext or ""))
                    bucket["sentiment_scores"].append(sentiment)

                for week_start, data in weekly_buckets.items():
                    avg_sentiment = (
                        sum(data["sentiment_scores"]) / len(data["sentiment_scores"])
                        if data["sentiment_scores"]
                        else 0.0
                    )
                    results.append(
                        {
                            "date": week_start,
                            "subreddit": sub_name,
                            "company": company,
                            "post_count": data["post_count"],
                            "comment_count": data["comment_count"],
                            "sentiment_score": round(avg_sentiment, 4),
                            "mention_count": data["mention_count"],
                            "source": "reddit",
                        }
                    )

            except Exception as e:
                logger.error(f"Error fetching Reddit data for r/{sub_name}: {e}")
                continue

        return results

    def _fetch_public(self, company: str) -> List[Dict[str, Any]]:
        """
        Fallback: scrape Reddit's public JSON API (no auth required).
        Fetches /new and /top posts for each subreddit and buckets them weekly.
        """
        subreddits = COMPANY_SUBREDDITS.get(company, [])
        results = []
        headers = {"User-Agent": "altdata-platform/1.0 (research bot)"}

        for sub_name in subreddits:
            weekly_buckets: Dict[str, Dict] = {}

            for feed in ("new", "top"):
                url = f"https://www.reddit.com/r/{sub_name}/{feed}.json"
                params = {"limit": 100, "t": "year"} if feed == "top" else {"limit": 100}
                try:
                    resp = requests.get(url, headers=headers, params=params, timeout=10)
                    if resp.status_code == 429:
                        time.sleep(5)
                        resp = requests.get(url, headers=headers, params=params, timeout=10)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    for child in posts:
                        post = child.get("data", {})
                        created = post.get("created_utc", 0)
                        if not created:
                            continue
                        post_date = datetime.utcfromtimestamp(created)
                        week_start = (post_date - timedelta(days=post_date.weekday())).strftime("%Y-%m-%d")
                        b = weekly_buckets.setdefault(week_start, {
                            "post_count": 0, "comment_count": 0,
                            "sentiment_scores": [], "mention_count": 0,
                            "total_score": 0,
                        })
                        b["post_count"] += 1
                        b["comment_count"] += int(post.get("num_comments", 0))
                        b["total_score"] += int(post.get("score", 0))
                        title = post.get("title", "") + " " + post.get("selftext", "")
                        b["sentiment_scores"].append(_simple_sentiment(title))
                        if company.lower() in title.lower() or sub_name.lower() in title.lower():
                            b["mention_count"] += 1
                    time.sleep(0.5)  # polite rate-limiting
                except Exception as e:
                    logger.error(f"[reddit_public] Error fetching r/{sub_name}/{feed}: {e}")
                    continue

            for week_start, b in weekly_buckets.items():
                avg_sent = sum(b["sentiment_scores"]) / len(b["sentiment_scores"]) if b["sentiment_scores"] else 0.0
                results.append({
                    "date": week_start,
                    "subreddit": sub_name,
                    "company": company,
                    "post_count": b["post_count"],
                    "comment_count": b["comment_count"],
                    "sentiment_score": round(avg_sent, 4),
                    "mention_count": b["mention_count"],
                    "avg_score": round(b["total_score"] / max(b["post_count"], 1), 1),
                    "source": "reddit",
                })

        logger.info(f"[reddit_public] Fetched {len(results)} weekly records for {company} (no-auth mode)")
        return results
