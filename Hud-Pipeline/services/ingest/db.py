from sqlalchemy import create_engine, String, Integer, DateTime, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import literal, or_, and_, ColumnElement
import datetime
from typing import Optional
from zoneinfo import ZoneInfo  # For explicit timezone handling (Python 3.9+)

# Database configuration
DATABASE_URL = "sqlite:///./hud.db"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True in development for SQL logging
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)  # expire_on_commit=False for performance in read-heavy apps


class Base(DeclarativeBase):
    """Base class for all ORM models. Provides common metadata."""


class NewsItem(Base):
    """
    Model representing a news item from RSS or HN.
    Stores unique items by URL to avoid duplicates during ingestion.
    """
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    source: Mapped[str] = mapped_column(
        String(100),  # e.g., 'bbc_rss', 'hackernews'
        nullable=False,
        index=True  # Optimize queries by source
    )
    title: Mapped[str] = mapped_column(
        String(500),  # Limit length for storage efficiency
        nullable=False
    )
    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        unique=True  # Prevent duplicate URLs across sources
    )
    popularity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0  # HN score or 0 for RSS
    )
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),  # Enable timezone-aware datetimes
        nullable=True,  # Allow None if no published date
        index=True  # For time-based queries
    )
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(ZoneInfo("UTC"))  # When fetched/ingested
    )
    # Optional short summary (50-120 chars) generated from title/description.
    summary: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Indexes for performance
    __table_args__ = (
        Index("ix_news_items_published_source", "published_at", "source"),  # Composite for common queries
    )

    @hybrid_property
    def is_recent(self) -> bool:
        """Hybrid property for easy filtering of recent items (e.g., last 24h)."""
        cutoff = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(hours=24)
        return self.published_at > cutoff if self.published_at else self.fetched_at > cutoff

    def _is_recent_expression() -> "ColumnElement[bool]":
        cutoff = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(hours=24)
        return or_(  # type: ignore
            and_(NewsItem.published_at.isnot(None), NewsItem.published_at > literal(cutoff)),  # type: ignore
            and_(NewsItem.published_at.is_(None), NewsItem.fetched_at > literal(cutoff))  # type: ignore
        )

    is_recent.expression = _is_recent_expression  # type: ignore

    def __repr__(self) -> str:
        return f"NewsItem(id={self.id}, title={self.title[:50]}..., url={self.url}, source={self.source})"


# Create tables if they don't exist (idempotent)
Base.metadata.create_all(bind=engine)
