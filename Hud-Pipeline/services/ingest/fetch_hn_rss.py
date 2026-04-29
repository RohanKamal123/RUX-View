import feedparser
import requests
import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError
from .db import SessionLocal, NewsItem
from services.summarizer import generate_summary

# Hacker News RSS feed
RSS_FEEDS = [
    "https://news.ycombinator.com/rss"
]

def fetch_hn_rss():
    session = SessionLocal()
    imported_count = 0
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:5]:  # fetch only 5 items for Day 1
            if not entry.get('link'):
                continue

            # Parse published_at if available
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                parsed = entry.published_parsed
                if isinstance(parsed, (tuple, list)) and len(parsed) >= 6:
                    try:
                        parts = [int(x) for x in parsed[:6]]  # type: ignore
                        year, month, day, hour, minute, second = parts
                        published_at = datetime.datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo("UTC"))
                    except (ValueError, TypeError):
                        pass  # Invalid date or non-int, leave as None

            item = NewsItem(
                source="hackernews",
                title=entry.title,
                url=entry.link,
                popularity=0,
                published_at=published_at,
                fetched_at=datetime.datetime.now(ZoneInfo("UTC"))
            )

            try:
                summary_content = entry.get('summary', '')
                if isinstance(summary_content, (list, type(None))):
                    if isinstance(summary_content, list):
                        summary_content = ' '.join(str(part) for part in summary_content)
                    else:
                        summary_content = ''
                title_content = entry.get('title', '')
                if isinstance(title_content, (list, type(None))):
                    if isinstance(title_content, list):
                        title_content = ' '.join(str(part) for part in title_content)
                    else:
                        title_content = ''
                text = summary_content + ' ' + title_content if summary_content else title_content
                item.summary = generate_summary(text)
            except Exception:
                item.summary = None

            session.add(item)
            try:
                session.commit()
                imported_count += 1
            except IntegrityError:
                session.rollback()  # Skip duplicate
        session.close()
    print(f"Fetched & stored {imported_count} items from HN RSS")

if __name__ == "__main__":
    fetch_hn_rss()
