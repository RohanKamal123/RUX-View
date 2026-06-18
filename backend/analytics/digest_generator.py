"""
digest_generator.py — Daily/Weekly Digest Generator for Vision OS.

Generates plain text security digests for three tier variants:
- Free: simple, max 200 words
- Household: detailed with person stats
- Business: detailed + shop analytics

Uses APScheduler for cron scheduling (D024).
All calls async (D026).
Plain text format (NO markdown — timestamp underscores break markdown).

Key Decisions:
- D014: Free tier gets digest (conversion hook)
- D024: APScheduler (NOT `schedule` library) — async-native
- D026: All calls async
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select

from backend.storage.database import AudioEvent, Event, PersonSighting

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────

TIER_WORD_LIMITS = {
    "free": 200,
    "household": 500,
    "business": 1000,
}

DEFAULT_TIER = "free"


# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class DigestData:
    """Data collected for digest generation."""

    user_id: str
    location_id: str
    date: date
    tier: str = "free"  # free/household/business
    events_summary: dict = field(default_factory=dict)
    person_stats: dict = field(default_factory=dict)
    audio_summary: dict = field(default_factory=dict)
    anomalies: list = field(default_factory=list)
    shop_data: Optional[dict] = None


# ── DigestGenerator ────────────────────────────────────────────


class DigestGenerator:
    """Generate daily and weekly security digests.

    Generates plain text digests tailored to user tier.
    Free tier gets simple summary (max 200 words).
    Household gets detailed with person stats.
    Business gets detailed + shop analytics.
    """

    def __init__(
        self,
        db_session_factory: Any,
        ai_client: Any,
        telegram_client: Any,
    ):
        """Initialize digest generator.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            ai_client: AI client for Gemini digest generation.
            telegram_client: TelegramClient for sending digests.
        """
        self.db_session_factory = db_session_factory
        self.ai_client = ai_client
        self.telegram = telegram_client

    async def generate_daily_digest(
        self,
        user_id: str,
        location_id: str,
        digest_date: date,
    ) -> str:
        """Generate daily digest for a user's location.

        Steps:
        1. Query events for the day
        2. Query person sightings
        3. Query audio events
        4. Query shop analytics (if business tier)
        5. Call Gemini to generate digest text
        6. Return formatted digest string

        Args:
            user_id: User to generate digest for.
            location_id: Location to generate digest for.
            digest_date: Date to generate digest for.

        Returns:
            Plain text digest (max 200 words for free tier).
        """
        # Get user tier
        tier = await self._get_user_tier(user_id)

        # Step 1: Query events for the day
        events_summary = await self._get_events_summary(
            user_id, location_id, digest_date
        )

        # Step 2: Query person sightings
        person_stats = await self._get_person_stats(
            user_id, location_id, digest_date
        )

        # Step 3: Query audio events
        audio_summary = await self._get_audio_summary(
            user_id, location_id, digest_date
        )

        # Step 4: Query shop analytics (business tier only)
        shop_data = None
        if tier == "business":
            shop_data = await self._get_shop_summary(
                user_id, location_id, digest_date
            )

        # Step 5: Generate digest text
        digest_data = DigestData(
            user_id=user_id,
            location_id=location_id,
            date=digest_date,
            tier=tier,
            events_summary=events_summary,
            person_stats=person_stats,
            audio_summary=audio_summary,
            shop_data=shop_data,
        )

        digest_text = await self._generate_digest_text(digest_data)

        # Step 6: Return formatted digest
        return digest_text

    async def generate_weekly_digest(
        self,
        user_id: str,
        location_id: str,
        week_start: date,
    ) -> str:
        """Generate weekly digest.

        Same as daily but aggregates 7 days of data.

        Args:
            user_id: User to generate digest for.
            location_id: Location to generate digest for.
            week_start: Start date of the week (Monday).

        Returns:
            Plain text weekly digest.
        """
        week_end = week_start + timedelta(days=6)
        tier = await self._get_user_tier(user_id)

        # Aggregate 7 days of events
        all_events = {"total": 0, "high": 0, "medium": 0, "low": 0}
        all_persons = {"total": 0, "familiar": 0, "unknown": 0}
        all_audio = {"total": 0, "top_class": "None", "top_time": ""}
        all_shop = None

        current = week_start
        while current <= week_end:
            events = await self._get_events_summary(user_id, location_id, current)
            for key in all_events:
                all_events[key] += events.get(key, 0)

            persons = await self._get_person_stats(user_id, location_id, current)
            for key in all_persons:
                all_persons[key] += persons.get(key, 0)

            audio = await self._get_audio_summary(user_id, location_id, current)
            all_audio["total"] += audio.get("total", 0)
            if audio.get("top_class") and audio["top_class"] != "None":
                all_audio["top_class"] = audio["top_class"]
                all_audio["top_time"] = audio.get("top_time", "")

            if tier == "business":
                shop = await self._get_shop_summary(user_id, location_id, current)
                if shop:
                    if all_shop is None:
                        all_shop = {
                            "total_customers": 0,
                            "peak_hour": None,
                            "avg_dwell": 0.0,
                        }
                    all_shop["total_customers"] += shop.get("total_customers", 0)

            current += timedelta(days=1)

        digest_data = DigestData(
            user_id=user_id,
            location_id=location_id,
            date=week_start,
            tier=tier,
            events_summary=all_events,
            person_stats=all_persons,
            audio_summary=all_audio,
            shop_data=all_shop,
        )

        digest_text = await self._generate_digest_text(digest_data, is_weekly=True)
        return digest_text

    async def send_daily_digests(self) -> int:
        """Send daily digests to ALL users.

        Called by APScheduler cron job at 22:00.

        Returns:
            Number of digests sent.
        """
        sent_count = 0
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import User, Location

                # Query all users with active subscriptions
                result = await session.execute(
                    select(User).where(User.subscription_active == True)  # noqa: E712
                )
                users = list(result.scalars().all())

                for user in users:
                    try:
                        # Get user's locations
                        loc_result = await session.execute(
                            select(Location).where(Location.user_id == user.id)
                        )
                        locations = list(loc_result.scalars().all())

                        for location in locations:
                            digest_date = datetime.now(timezone.utc).date()
                            digest = await self.generate_daily_digest(
                                user_id=user.id,
                                location_id=location.id,
                                digest_date=digest_date,
                            )

                            if digest and user.telegram_chat_id:
                                await self.telegram.send_text(
                                    user.telegram_chat_id, digest
                                )
                                sent_count += 1
                                logger.info(
                                    "Daily digest sent to user %s for location %s",
                                    user.id, location.id,
                                )
                    except Exception as exc:
                        logger.error(
                            "Failed to send digest for user %s: %s",
                            user.id, exc, exc_info=True,
                        )

        except Exception as exc:
            logger.error("send_daily_digests failed: %s", exc, exc_info=True)

        logger.info("Daily digests sent: %d", sent_count)
        return sent_count

    async def send_weekly_digests(self) -> int:
        """Send weekly digests to ALL users.

        Called by APScheduler cron job Monday 08:00.

        Returns:
            Number of digests sent.
        """
        sent_count = 0
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import User, Location

                result = await session.execute(
                    select(User).where(User.subscription_active == True)  # noqa: E712
                )
                users = list(result.scalars().all())

                # Calculate week start (last Monday)
                today = datetime.now(timezone.utc).date()
                week_start = today - timedelta(days=today.weekday())

                for user in users:
                    try:
                        loc_result = await session.execute(
                            select(Location).where(Location.user_id == user.id)
                        )
                        locations = list(loc_result.scalars().all())

                        for location in locations:
                            digest = await self.generate_weekly_digest(
                                user_id=user.id,
                                location_id=location.id,
                                week_start=week_start,
                            )

                            if digest and user.telegram_chat_id:
                                await self.telegram.send_text(
                                    user.telegram_chat_id, digest
                                )
                                sent_count += 1
                    except Exception as exc:
                        logger.error(
                            "Failed to send weekly digest for user %s: %s",
                            user.id, exc, exc_info=True,
                        )

        except Exception as exc:
            logger.error("send_weekly_digests failed: %s", exc, exc_info=True)

        logger.info("Weekly digests sent: %d", sent_count)
        return sent_count

    def _format_free_digest(
        self,
        events_summary: dict,
        person_stats: dict,
    ) -> str:
        """Format free tier digest (max 200 words).

        Template:
        VisionOS Daily - {date}
        {camera}: {count} events, {high_count} HIGH
        Visitors: {total} ({familiar} familiar, {unknown} unknown)
        Audio: {audio_count} alerts
        All clear today.

        Args:
            events_summary: Dict with event counts.
            person_stats: Dict with person stats.

        Returns:
            Formatted plain text digest.
        """
        lines = [
            f"VisionOS Daily - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            f"Events: {events_summary.get('total', 0)} total, "
            f"{events_summary.get('high', 0)} HIGH",
            f"Visitors: {person_stats.get('total', 0)} "
            f"({person_stats.get('familiar', 0)} familiar, "
            f"{person_stats.get('unknown', 0)} unknown)",
            f"Audio: {events_summary.get('audio_count', 0)} alerts",
        ]

        if events_summary.get("total", 0) == 0:
            lines.append("All clear today.")

        return "\n".join(lines)

    def _format_household_digest(
        self,
        events_summary: dict,
        person_stats: dict,
        audio_summary: dict,
    ) -> str:
        """Format household tier digest (detailed).

        Template:
        VisionOS Daily Summary - {date}
        [Location: {name}]

        Security: {total} events total
          HIGH: {high}  MEDIUM: {medium}  LOW: {low}
        Visitors: {total_visitors} ({familiar} familiar, {unknown} unknown)
        {person_uid} seen {count}x - flagged
        Audio: {audio_count} events ({top_class} {time})
        Gate status: {gate_status}

        Args:
            events_summary: Dict with event counts.
            person_stats: Dict with person stats.
            audio_summary: Dict with audio stats.

        Returns:
            Formatted plain text digest.
        """
        lines = [
            f"VisionOS Daily Summary - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "",
            f"Security: {events_summary.get('total', 0)} events total",
            f"  HIGH: {events_summary.get('high', 0)}  "
            f"MEDIUM: {events_summary.get('medium', 0)}  "
            f"LOW: {events_summary.get('low', 0)}",
            f"Visitors: {person_stats.get('total', 0)} "
            f"({person_stats.get('familiar', 0)} familiar, "
            f"{person_stats.get('unknown', 0)} unknown)",
        ]

        # Add flagged persons
        flagged = person_stats.get("flagged", [])
        for person in flagged[:3]:  # Max 3 flagged
            lines.append(
                f"{person.get('person_uid', 'Unknown')} seen "
                f"{person.get('count', 1)}x - flagged"
            )

        # Audio summary
        audio_count = audio_summary.get("total", 0)
        if audio_count > 0:
            lines.append(
                f"Audio: {audio_count} events "
                f"({audio_summary.get('top_class', 'N/A')} "
                f"{audio_summary.get('top_time', '')})"
            )
        else:
            lines.append("Audio: No audio events")

        return "\n".join(lines)

    def _format_business_digest(
        self,
        events_summary: dict,
        person_stats: dict,
        audio_summary: dict,
        shop_data: Optional[dict],
    ) -> str:
        """Format business tier digest (detailed + analytics).

        Includes shop analytics section.

        Args:
            events_summary: Dict with event counts.
            person_stats: Dict with person stats.
            audio_summary: Dict with audio stats.
            shop_data: Optional shop analytics data.

        Returns:
            Formatted plain text digest.
        """
        lines = [
            f"VisionOS Daily Summary - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "",
            f"Security: {events_summary.get('total', 0)} events total",
            f"  HIGH: {events_summary.get('high', 0)}  "
            f"MEDIUM: {events_summary.get('medium', 0)}  "
            f"LOW: {events_summary.get('low', 0)}",
            f"Visitors: {person_stats.get('total', 0)} "
            f"({person_stats.get('familiar', 0)} familiar, "
            f"{person_stats.get('unknown', 0)} unknown)",
        ]

        # Add flagged persons
        flagged = person_stats.get("flagged", [])
        for person in flagged[:3]:
            lines.append(
                f"{person.get('person_uid', 'Unknown')} seen "
                f"{person.get('count', 1)}x - flagged"
            )

        # Audio summary
        audio_count = audio_summary.get("total", 0)
        if audio_count > 0:
            lines.append(
                f"Audio: {audio_count} events "
                f"({audio_summary.get('top_class', 'N/A')})"
            )
        else:
            lines.append("Audio: No audio events")

        # Shop analytics section
        if shop_data:
            lines.extend([
                "",
                "Shop Analytics:",
                f"  Customers: {shop_data.get('total_customers', 0)}",
                f"  Peak hour: {shop_data.get('peak_hour', 'N/A')}:00",
                f"  Avg dwell: {shop_data.get('avg_dwell', 0):.0f}s",
            ])

        return "\n".join(lines)

    def _get_tier_limit(self, tier: str) -> int:
        """Get word limit for tier.

        Args:
            tier: User tier (free/household/business).

        Returns:
            Word limit for the tier.
        """
        return TIER_WORD_LIMITS.get(tier, TIER_WORD_LIMITS[DEFAULT_TIER])

    async def _generate_digest_text(
        self, digest_data: DigestData, is_weekly: bool = False
    ) -> str:
        """Generate digest text using template or Gemini.

        Args:
            digest_data: Collected digest data.
            is_weekly: Whether this is a weekly digest.

        Returns:
            Formatted plain text digest.
        """
        tier = digest_data.tier
        word_limit = self._get_tier_limit(tier)

        if tier == "free":
            text = self._format_free_digest(
                digest_data.events_summary,
                digest_data.person_stats,
            )
        elif tier == "household":
            text = self._format_household_digest(
                digest_data.events_summary,
                digest_data.person_stats,
                digest_data.audio_summary,
            )
        elif tier == "business":
            text = self._format_business_digest(
                digest_data.events_summary,
                digest_data.person_stats,
                digest_data.audio_summary,
                digest_data.shop_data,
            )
        else:
            text = self._format_free_digest(
                digest_data.events_summary,
                digest_data.person_stats,
            )

        # Truncate to word limit if needed
        words = text.split()
        if len(words) > word_limit:
            text = " ".join(words[:word_limit]) + "..."

        return text

    async def _get_user_tier(self, user_id: str) -> str:
        """Get user's subscription tier.

        Args:
            user_id: User ID.

        Returns:
            Tier string (free/household/business).
        """
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import User

                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    return user.tier
        except Exception as exc:
            logger.error("Failed to get user tier: %s", exc)

        return DEFAULT_TIER

    async def _get_events_summary(
        self, user_id: str, location_id: str, query_date: date
    ) -> dict:
        """Get summary of events for a date.

        Args:
            user_id: User ID.
            location_id: Location ID.
            query_date: Date to query.

        Returns:
            Dict with total, high, medium, low counts.
        """
        summary = {"total": 0, "high": 0, "medium": 0, "low": 0, "audio_count": 0}
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(query_date, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(query_date, datetime.max.time(), tzinfo=timezone.utc)

                result = await session.execute(
                    select(Event).where(
                        and_(
                            Event.user_id == user_id,
                            Event.location_id == location_id,
                            Event.timestamp_start >= start,
                            Event.timestamp_start <= end,
                        )
                    )
                )
                events = list(result.scalars().all())

                summary["total"] = len(events)
                for event in events:
                    tl = (event.threat_level or "LOW").upper()
                    if tl == "HIGH":
                        summary["high"] += 1
                    elif tl == "MEDIUM":
                        summary["medium"] += 1
                    else:
                        summary["low"] += 1

                # Count audio events
                audio_result = await session.execute(
                    select(func.count(AudioEvent.id)).where(
                        and_(
                            AudioEvent.user_id == user_id,
                            AudioEvent.timestamp >= start,
                            AudioEvent.timestamp <= end,
                        )
                    )
                )
                summary["audio_count"] = audio_result.scalar() or 0

        except Exception as exc:
            logger.error("Failed to get events summary: %s", exc)

        return summary

    async def _get_person_stats(
        self, user_id: str, location_id: str, query_date: date
    ) -> dict:
        """Get person sighting stats for a date.

        Args:
            user_id: User ID.
            location_id: Location ID.
            query_date: Date to query.

        Returns:
            Dict with total, familiar, unknown counts and flagged list.
        """
        stats = {"total": 0, "familiar": 0, "unknown": 0, "flagged": []}
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(query_date, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(query_date, datetime.max.time(), tzinfo=timezone.utc)

                result = await session.execute(
                    select(PersonSighting).where(
                        and_(
                            PersonSighting.user_id == user_id,
                            PersonSighting.timestamp >= start,
                            PersonSighting.timestamp <= end,
                        )
                    )
                )
                sightings = list(result.scalars().all())

                # Count unique persons
                unique_persons = set()
                person_counts = {}
                for s in sightings:
                    unique_persons.add(s.person_uid)
                    person_counts[s.person_uid] = person_counts.get(s.person_uid, 0) + 1

                stats["total"] = len(unique_persons)

                # Check which persons are familiar (have history)
                for puid in unique_persons:
                    person_result = await session.execute(
                        select(func.count(PersonSighting.id)).where(
                            PersonSighting.person_uid == puid
                        )
                    )
                    total_sightings = person_result.scalar() or 0
                    if total_sightings > 1:
                        stats["familiar"] += 1
                    else:
                        stats["unknown"] += 1

                    # Flag persons seen 3+ times today
                    if person_counts.get(puid, 0) >= 3:
                        stats["flagged"].append({
                            "person_uid": puid,
                            "count": person_counts[puid],
                        })

        except Exception as exc:
            logger.error("Failed to get person stats: %s", exc)

        return stats

    async def _get_audio_summary(
        self, user_id: str, location_id: str, query_date: date
    ) -> dict:
        """Get audio event summary for a date.

        Args:
            user_id: User ID.
            location_id: Location ID.
            query_date: Date to query.

        Returns:
            Dict with total, top_class, top_time.
        """
        summary = {"total": 0, "top_class": "None", "top_time": ""}
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(query_date, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(query_date, datetime.max.time(), tzinfo=timezone.utc)

                result = await session.execute(
                    select(AudioEvent).where(
                        and_(
                            AudioEvent.user_id == user_id,
                            AudioEvent.timestamp >= start,
                            AudioEvent.timestamp <= end,
                        )
                    ).order_by(AudioEvent.timestamp.desc())
                )
                audio_events = list(result.scalars().all())

                summary["total"] = len(audio_events)
                if audio_events:
                    # Find most common class
                    class_counts = {}
                    for ae in audio_events:
                        cls = ae.yamnet_class or "Unknown"
                        class_counts[cls] = class_counts.get(cls, 0) + 1

                    top_class = max(class_counts, key=class_counts.get)
                    summary["top_class"] = top_class

                    # Get time of first occurrence
                    first = audio_events[-1]
                    if first.timestamp:
                        summary["top_time"] = first.timestamp.strftime("%H:%M")

        except Exception as exc:
            logger.error("Failed to get audio summary: %s", exc)

        return summary

    async def _get_shop_summary(
        self, user_id: str, location_id: str, query_date: date
    ) -> Optional[dict]:
        """Get shop analytics summary for a date.

        Args:
            user_id: User ID.
            location_id: Location ID.
            query_date: Date to query.

        Returns:
            Dict with shop analytics or None.
        """
        try:
            from backend.analytics.shop_analytics import ShopAnalytics

            shop = ShopAnalytics(db_session_factory=self.db_session_factory)
            summary = await shop.get_daily_summary(location_id, query_date)

            return {
                "total_customers": summary.total_customers,
                "peak_hour": summary.peak_hour,
                "avg_dwell": summary.avg_dwell_seconds,
                "gender_breakdown": summary.gender_breakdown,
            }
        except Exception as exc:
            logger.error("Failed to get shop summary: %s", exc)
            return None
