"""
report_builder.py — Business Tier Report Builder for Vision OS.

Builds comprehensive weekly business reports with security analytics,
person tracking, audio events, shop analytics, and AI-generated
security recommendations.

Key Decisions:
- D014: Business tier only
- D026: All calls async
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select

from backend.storage.database import AudioEvent, Event, PersonSighting

logger = logging.getLogger(__name__)


# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class BusinessReport:
    """Comprehensive weekly business report."""

    location_name: str
    week_start: date
    week_end: date
    total_events: int = 0
    high_threat_events: int = 0
    unique_persons: int = 0
    repeat_offenders: list = field(default_factory=list)
    audio_events: int = 0
    shop_analytics: Optional[dict] = None
    recommendations: list = field(default_factory=list)


# ── ReportBuilder ──────────────────────────────────────────────


class ReportBuilder:
    """Build business-tier detailed reports.

    Generates comprehensive weekly reports with security analytics,
    person tracking, audio events, shop analytics, and AI recommendations.
    """

    def __init__(self, db_session_factory: Any, ai_client: Any):
        """Initialize report builder.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            ai_client: AI client for Gemini recommendation generation.
        """
        self.db_session_factory = db_session_factory
        self.ai_client = ai_client

    async def build_weekly_report(
        self,
        user_id: str,
        location_id: str,
        week_start: date,
    ) -> BusinessReport:
        """Build a comprehensive weekly business report.

        Args:
            user_id: User ID.
            location_id: Location ID.
            week_start: Start date of the week (Monday).

        Returns:
            BusinessReport with all sections.
        """
        week_end = week_start + timedelta(days=6)

        # Get location name
        location_name = await self._get_location_name(location_id)

        # Query events for the week
        events = await self._get_weekly_events(user_id, location_id, week_start, week_end)
        total_events = len(events)
        high_threat_events = sum(
            1 for e in events if (e.threat_level or "LOW").upper() == "HIGH"
        )

        # Query unique persons
        unique_persons = await self._get_unique_persons(
            user_id, location_id, week_start, week_end
        )

        # Query repeat offenders
        repeat_offenders = await self._get_repeat_offenders(
            user_id, location_id, week_start, week_end
        )

        # Query audio events
        audio_events = await self._get_audio_event_count(
            user_id, location_id, week_start, week_end
        )

        # Query shop analytics
        shop_analytics = await self._get_weekly_shop_analytics(
            location_id, week_start, week_end
        )

        # Build report
        report = BusinessReport(
            location_name=location_name,
            week_start=week_start,
            week_end=week_end,
            total_events=total_events,
            high_threat_events=high_threat_events,
            unique_persons=unique_persons,
            repeat_offenders=repeat_offenders,
            audio_events=audio_events,
            shop_analytics=shop_analytics,
        )

        # Generate recommendations
        report.recommendations = await self._get_recommendations(report)

        return report

    async def _get_recommendations(
        self, report: BusinessReport
    ) -> list[str]:
        """Generate security recommendations based on report data.

        Uses Gemini to analyse patterns and suggest improvements.

        Args:
            report: The business report to generate recommendations for.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        # Rule-based recommendations
        if report.high_threat_events > 5:
            recommendations.append(
                f"High threat events are elevated ({report.high_threat_events} this week). "
                f"Consider reviewing camera placement and increasing patrol frequency."
            )

        if report.repeat_offenders:
            offender_ids = [o["person_uid"] for o in report.repeat_offenders[:3]]
            recommendations.append(
                f"Repeat offenders detected: {', '.join(offender_ids)}. "
                f"Flag these individuals for monitoring."
            )

        if report.audio_events > 20:
            recommendations.append(
                f"Audio events are high ({report.audio_events} this week). "
                f"Review audio sensitivity settings."
            )

        if report.shop_analytics:
            peak_hour = report.shop_analytics.get("peak_hour")
            if peak_hour is not None:
                recommendations.append(
                    f"Peak business hour is {peak_hour}:00. "
                    f"Ensure adequate staffing during this time."
                )

        # Default recommendation if none triggered
        if not recommendations:
            recommendations.append(
                "No significant security concerns this week. Continue regular monitoring."
            )

        # Try Gemini for AI-powered recommendations
        try:
            prompt = self._build_recommendation_prompt(report)
            response = await self.ai_client.generate_content_async(prompt)
            if response and response.text:
                ai_recs = [
                    line.strip()
                    for line in response.text.split("\n")
                    if line.strip() and not line.startswith("#")
                ]
                recommendations.extend(ai_recs[:2])  # Add up to 2 AI recommendations
        except Exception as exc:
            logger.warning("Failed to generate AI recommendations: %s", exc)

        return recommendations

    def format_report_text(self, report: BusinessReport) -> str:
        """Format report as plain text for Telegram.

        NO markdown formatting.

        Args:
            report: The business report to format.

        Returns:
            Plain text report string.
        """
        lines = [
            f"VisionOS Weekly Report",
            f"Location: {report.location_name}",
            f"Week: {report.week_start.isoformat()} to {report.week_end.isoformat()}",
            "",
            "--- Security Summary ---",
            f"Total events: {report.total_events}",
            f"High threat events: {report.high_threat_events}",
            f"Unique persons detected: {report.unique_persons}",
            f"Audio events: {report.audio_events}",
        ]

        # Repeat offenders
        if report.repeat_offenders:
            lines.extend([
                "",
                "--- Repeat Offenders ---",
            ])
            for offender in report.repeat_offenders[:5]:
                lines.append(
                    f"{offender.get('person_uid', 'Unknown')}: "
                    f"{offender.get('count', 0)} sightings"
                )

        # Shop analytics
        if report.shop_analytics:
            lines.extend([
                "",
                "--- Shop Analytics ---",
                f"Total customers: {report.shop_analytics.get('total_customers', 0)}",
                f"Peak hour: {report.shop_analytics.get('peak_hour', 'N/A')}:00",
                f"Avg dwell time: {report.shop_analytics.get('avg_dwell', 0):.0f}s",
                f"Repeat rate: {report.shop_analytics.get('repeat_rate', 0):.1f}%",
            ])

        # Recommendations
        if report.recommendations:
            lines.extend([
                "",
                "--- Recommendations ---",
            ])
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)

    def _build_recommendation_prompt(self, report: BusinessReport) -> str:
        """Build prompt for Gemini recommendation generation.

        Args:
            report: The business report data.

        Returns:
            Prompt string for Gemini.
        """
        return (
            f"Based on this weekly security report for {report.location_name}, "
            f"provide 2 specific security recommendations:\n"
            f"- Total events: {report.total_events}\n"
            f"- High threat events: {report.high_threat_events}\n"
            f"- Unique persons: {report.unique_persons}\n"
            f"- Repeat offenders: {len(report.repeat_offenders)}\n"
            f"- Audio events: {report.audio_events}\n"
            f"Keep recommendations concise and actionable."
        )

    async def _get_location_name(self, location_id: str) -> str:
        """Get location name from database.

        Args:
            location_id: Location ID.

        Returns:
            Location name string.
        """
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import Location

                result = await session.execute(
                    select(Location).where(Location.id == location_id)
                )
                location = result.scalar_one_or_none()
                if location:
                    return location.name or location_id
        except Exception as exc:
            logger.error("Failed to get location name: %s", exc)

        return location_id

    async def _get_weekly_events(
        self,
        user_id: str,
        location_id: str,
        week_start: date,
        week_end: date,
    ) -> list:
        """Get all events for a week.

        Args:
            user_id: User ID.
            location_id: Location ID.
            week_start: Week start date.
            week_end: Week end date.

        Returns:
            List of Event objects.
        """
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)

                result = await session.execute(
                    select(Event).where(
                        and_(
                            Event.user_id == user_id,
                            Event.location_id == location_id,
                            Event.timestamp_start >= start,
                            Event.timestamp_start <= end,
                        )
                    ).order_by(Event.timestamp_start)
                )
                return list(result.scalars().all())
        except Exception as exc:
            logger.error("Failed to get weekly events: %s", exc)
            return []

    async def _get_unique_persons(
        self,
        user_id: str,
        location_id: str,
        week_start: date,
        week_end: date,
    ) -> int:
        """Count unique persons detected in a week.

        Args:
            user_id: User ID.
            location_id: Location ID.
            week_start: Week start date.
            week_end: Week end date.

        Returns:
            Count of unique persons.
        """
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)

                result = await session.execute(
                    select(func.count(func.distinct(PersonSighting.person_uid)))
                    .where(
                        and_(
                            PersonSighting.user_id == user_id,
                            PersonSighting.timestamp >= start,
                            PersonSighting.timestamp <= end,
                        )
                    )
                )
                return result.scalar() or 0
        except Exception as exc:
            logger.error("Failed to count unique persons: %s", exc)
            return 0

    async def _get_repeat_offenders(
        self,
        user_id: str,
        location_id: str,
        week_start: date,
        week_end: date,
    ) -> list[dict]:
        """Get persons with multiple sightings in a week.

        Args:
            user_id: User ID.
            location_id: Location ID.
            week_start: Week start date.
            week_end: Week end date.

        Returns:
            List of dicts with person_uid and count.
        """
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)

                # Group by person_uid and count
                result = await session.execute(
                    select(
                        PersonSighting.person_uid,
                        func.count(PersonSighting.id).label("sighting_count"),
                    )
                    .where(
                        and_(
                            PersonSighting.user_id == user_id,
                            PersonSighting.timestamp >= start,
                            PersonSighting.timestamp <= end,
                        )
                    )
                    .group_by(PersonSighting.person_uid)
                    .having(func.count(PersonSighting.id) >= 3)
                    .order_by(func.count(PersonSighting.id).desc())
                )
                rows = result.all()
                return [
                    {"person_uid": row.person_uid, "count": row.sighting_count}
                    for row in rows
                ]
        except Exception as exc:
            logger.error("Failed to get repeat offenders: %s", exc)
            return []

    async def _get_audio_event_count(
        self,
        user_id: str,
        location_id: str,
        week_start: date,
        week_end: date,
    ) -> int:
        """Count audio events in a week.

        Args:
            user_id: User ID.
            location_id: Location ID.
            week_start: Week start date.
            week_end: Week end date.

        Returns:
            Count of audio events.
        """
        try:
            async with self.db_session_factory() as session:
                start = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
                end = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)

                result = await session.execute(
                    select(func.count(AudioEvent.id))
                    .where(
                        and_(
                            AudioEvent.user_id == user_id,
                            AudioEvent.timestamp >= start,
                            AudioEvent.timestamp <= end,
                        )
                    )
                )
                return result.scalar() or 0
        except Exception as exc:
            logger.error("Failed to count audio events: %s", exc)
            return 0

    async def _get_weekly_shop_analytics(
        self,
        location_id: str,
        week_start: date,
        week_end: date,
    ) -> Optional[dict]:
        """Get aggregated shop analytics for a week.

        Args:
            location_id: Location ID.
            week_start: Week start date.
            week_end: Week end date.

        Returns:
            Dict with weekly shop analytics or None.
        """
        try:
            from backend.analytics.shop_analytics import ShopAnalytics

            shop = ShopAnalytics(db_session_factory=self.db_session_factory)
            report = await shop.get_weekly_report(location_id, week_start)
            return report
        except Exception as exc:
            logger.warning("Failed to get weekly shop analytics: %s", exc)
            return None
