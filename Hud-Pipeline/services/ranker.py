from typing import List
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .ingest.db import NewsItem

def calculate_score(item: NewsItem) -> float:
    """
    Calculate ranking score for a news item.
    Score = 0.4 * recency + 0.5 * popularity + 0.1 * random
    - Recency: 1 for now, decreases linearly to 0 over 24 hours from fetched_at or published_at.
    - Popularity: normalized score / 1000 (assume max 1000).
    - Random: small factor for diversity [0, 0.1].
    """
    now = datetime.now(ZoneInfo("UTC"))
    time_ref = item.published_at if item.published_at else item.fetched_at
    
    # Ensure time_ref is timezone-aware
    if time_ref.tzinfo is None:
        time_ref = time_ref.replace(tzinfo=ZoneInfo("UTC"))
    
    hours_old = (now - time_ref).total_seconds() / 3600
    recency = max(0, 1 - (hours_old / 24.0))
    popularity_norm = min(item.popularity / 1000.0, 1.0)
    rand_factor = random.uniform(0, 0.1)
    score = 0.4 * recency + 0.5 * popularity_norm + 0.1 * rand_factor
    return score

def rank_items(items: List[NewsItem]) -> List[NewsItem]:
    """
    Rank a list of news items by calculated score, descending.
    """
    scored = [(item, calculate_score(item)) for item in items]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [item for item, score in scored]
