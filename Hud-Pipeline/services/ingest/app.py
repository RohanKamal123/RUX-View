from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import feedparser
import requests
from typing import List, Optional
import datetime
from zoneinfo import ZoneInfo
from .db import SessionLocal, NewsItem
from .schemas import NewsOut
from ..ranker import rank_items
from services.summarizer import generate_summary

app = FastAPI(
    title="RSS and HN API Service",
    description="FastAPI service to fetch RSS feeds and Hacker News stories",
    version="1.0.0"
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "Welcome to RSS and HN API Service"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/rss")
async def get_rss(db: Session = Depends(get_db)):
    feed_url = "http://feeds.bbci.co.uk/news/rss.xml"  # BBC News RSS
    try:
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            return {"imported_count": 0, "total_entries": 0, "error": "No entries in feed"}
    except Exception as e:
        return {"imported_count": 0, "total_entries": 0, "error": f"Failed to parse feed: {str(e)}"}

    imported_count = 0
    for entry in feed.entries:
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
            source="bbc_rss",
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

        db.add(item)
        try:
            db.commit()
            imported_count += 1
        except IntegrityError:
            db.rollback()  # Skip duplicate

    return {"imported_count": imported_count, "total_entries": len(feed.entries)}
