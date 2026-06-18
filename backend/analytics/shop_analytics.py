"""
shop_analytics.py — Shop Analytics Module for Vision OS.

Business tier only feature. Tracks customer entries, demographics,
peak hours, dwell time, and repeat customer frequency.
Staff filtered out via Re-ID (staff profiles) or staff entrance zone.

Key Decisions:
- D008: Five separate modes (shop mode is one of them)
- D014: Shop analytics exclusive to Business tier
- D026: All calls async
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, desc, func, select

from backend.storage.database import ShopAnalytic

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────

MIN_DWELL_SECONDS = 30  # Minimum dwell time to count


# ── Dataclasses ────────────────────────────────────────────────


@dataclass
class CustomerEntry:
    """A customer entry event recorded by a camera."""

    person_uid: str
    camera_id: str
    timestamp: datetime
    gender: str = "unknown"  # male/female/unknown
    age_group: str = "unknown"  # teen/20s/30s/40s/50s+/unknown
    is_staff: bool = False
    dwell_seconds: Optional[float] = None
    visit_count_today: int = 1


@dataclass
class HourlyAnalytics:
    """Aggregated analytics for a single hour bucket."""

    camera_id: str
    date: date
    hour: int
    customer_count: int = 0
    male_count: int = 0
    female_count: int = 0
    unknown_gender: int = 0
    age_teens: int = 0
    age_20s: int = 0
    age_30s: int = 0
    age_40s: int = 0
    age_50plus: int = 0
    avg_dwell_seconds: float = 0.0


@dataclass
class DailySummary:
    """Summary of a full day's shop analytics."""

    camera_id: str
    date: date
    total_customers: int = 0
    unique_customers: int = 0
    staff_count: int = 0
    gender_breakdown: dict = field(default_factory=lambda: {"male": 0, "female": 0, "unknown": 0})
    age_breakdown: dict = field(
        default_factory=lambda: {"teens": 0, "20s": 0, "30s": 0, "40s": 0, "50plus": 0}
    )
    peak_hour: Optional[int] = None
    avg_dwell_seconds: float = 0.0
    repeat_customers: int = 0


# ── Age Group Helpers ──────────────────────────────────────────

AGE_GROUP_MAP = {
    "child": "teens",
    "teen": "teens",
    "20s": "20s",
    "30s": "30s",
    "40s": "40s",
    "50s": "50plus",
    "60+": "50plus",
    "unknown": "unknown",
}


def _map_age_group(gemma_age_group: str) -> str:
    """Map Gemma age group to analytics bucket.

    Args:
        gemma_age_group: Age group from Gemma analysis.

    Returns:
        Normalized age group key.
    """
    return AGE_GROUP_MAP.get(gemma_age_group, "unknown")


# ── ShopAnalytics ──────────────────────────────────────────────


class ShopAnalytics:
    """Shop analytics aggregation and reporting.

    Tracks customer entries, demographics, peak hours, dwell time,
    and repeat customer frequency. Staff are filtered out.
    """

    def __init__(self, db_session_factory: Any):
        """Initialize shop analytics.

        Args:
            db_session_factory: SQLAlchemy async session factory.
        """
        self.db_session_factory = db_session_factory

    async def record_entry(
        self,
        camera_id: str,
        user_id: str,
        timestamp: datetime,
        gemma_result: dict,
        person_uid: Optional[str] = None,
        is_staff: bool = False,
    ) -> CustomerEntry:
        """Record a customer entry event.

        Steps:
        1. Extract gender + age from gemma_result
        2. Check if person is staff (Re-ID match or staff entrance)
        3. Upsert hourly analytics bucket
        4. Track repeat visits today

        Args:
            camera_id: Camera that detected the entry.
            user_id: User who owns the camera.
            timestamp: When the entry was detected.
            gemma_result: Gemma analysis result dict.
            person_uid: Optional person UID for Re-ID tracking.
            is_staff: Whether this person is identified as staff.

        Returns:
            CustomerEntry with entry details.
        """
        # Step 1: Extract gender + age from gemma_result
        gender = gemma_result.get("gender", "unknown")
        age_group = _map_age_group(gemma_result.get("age_group", "unknown"))

        # Generate person_uid if not provided
        if not person_uid:
            person_uid = f"P_{timestamp.strftime('%Y%m%d%H%M%S')}_{camera_id}"

        # Step 2: Check if staff
        if is_staff:
            logger.info("Staff entry filtered out: %s at %s", person_uid, camera_id)
            return CustomerEntry(
                person_uid=person_uid,
                camera_id=camera_id,
                timestamp=timestamp,
                gender=gender,
                age_group=age_group,
                is_staff=True,
            )

        # Step 3: Upsert hourly analytics bucket
        entry_hour = timestamp.hour
        entry_date = timestamp.date()

        async with self.db_session_factory() as session:
            # Find or create hourly bucket
            result = await session.execute(
                select(ShopAnalytic).where(
                    and_(
                        ShopAnalytic.camera_id == camera_id,
                        ShopAnalytic.date == entry_date,
                        ShopAnalytic.hour == entry_hour,
                    )
                )
            )
            bucket = result.scalar_one_or_none()

            if bucket:
                # Update existing bucket
                bucket.customer_count += 1
                if gender == "male":
                    bucket.male_count += 1
                elif gender == "female":
                    bucket.female_count += 1
                else:
                    bucket.unknown_gender += 1

                if age_group == "teens":
                    bucket.age_teens += 1
                elif age_group == "20s":
                    bucket.age_20s += 1
                elif age_group == "30s":
                    bucket.age_30s += 1
                elif age_group == "40s":
                    bucket.age_40s += 1
                elif age_group == "50plus":
                    bucket.age_50plus += 1
            else:
                # Create new bucket
                bucket = ShopAnalytic(
                    camera_id=camera_id,
                    user_id=user_id,
                    date=entry_date,
                    hour=entry_hour,
                    customer_count=1,
                    male_count=1 if gender == "male" else 0,
                    female_count=1 if gender == "female" else 0,
                    unknown_gender=1 if gender == "unknown" else 0,
                    age_teens=1 if age_group == "teens" else 0,
                    age_20s=1 if age_group == "20s" else 0,
                    age_30s=1 if age_group == "30s" else 0,
                    age_40s=1 if age_group == "40s" else 0,
                    age_50plus=1 if age_group == "50plus" else 0,
                )
                session.add(bucket)

            await session.flush()
            await session.commit()

        # Step 4: Track repeat visits (simplified — counts per day)
        visit_count = await self._get_visit_count_today(
            camera_id, user_id, person_uid, entry_date
        )

        logger.info(
            "Customer entry recorded: %s at %s (gender=%s, age=%s, visit=%d)",
            person_uid, camera_id, gender, age_group, visit_count,
        )

        return CustomerEntry(
            person_uid=person_uid,
            camera_id=camera_id,
            timestamp=timestamp,
            gender=gender,
            age_group=age_group,
            is_staff=False,
            visit_count_today=visit_count,
        )

    async def record_exit(
        self,
        person_uid: str,
        camera_id: str,
        entry_timestamp: datetime,
        exit_timestamp: datetime,
    ) -> None:
        """Record customer exit to calculate dwell time.

        Updates avg_dwell_seconds for the relevant hour bucket.

        Args:
            person_uid: Person UID.
            camera_id: Camera that detected the exit.
            entry_timestamp: When the person entered.
            exit_timestamp: When the person exited.
        """
        dwell = self._calculate_dwell(entry_timestamp, exit_timestamp)
        if dwell is None:
            return

        entry_hour = entry_timestamp.hour
        entry_date = entry_timestamp.date()

        async with self.db_session_factory() as session:
            result = await session.execute(
                select(ShopAnalytic).where(
                    and_(
                        ShopAnalytic.camera_id == camera_id,
                        ShopAnalytic.date == entry_date,
                        ShopAnalytic.hour == entry_hour,
                    )
                )
            )
            bucket = result.scalar_one_or_none()

            if bucket:
                # Update average dwell time
                if bucket.avg_dwell_seconds:
                    # Weighted average
                    total_dwell = bucket.avg_dwell_seconds * bucket.customer_count
                    total_dwell += dwell
                    bucket.avg_dwell_seconds = total_dwell / bucket.customer_count
                else:
                    bucket.avg_dwell_seconds = dwell

                await session.flush()
                await session.commit()

    async def get_hourly_breakdown(
        self, camera_id: str, analytics_date: date
    ) -> list[HourlyAnalytics]:
        """Get hourly breakdown for a camera on a specific date.

        Args:
            camera_id: Camera to get analytics for.
            analytics_date: Date to get analytics for.

        Returns:
            List of HourlyAnalytics (24 entries, 0-23).
        """
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(ShopAnalytic)
                .where(
                    and_(
                        ShopAnalytic.camera_id == camera_id,
                        ShopAnalytic.date == analytics_date,
                    )
                )
                .order_by(ShopAnalytic.hour)
            )
            buckets = list(result.scalars().all())

        # Build 24-hour array, filling gaps with empty buckets
        bucket_map = {b.hour: b for b in buckets}
        hourly = []
        for h in range(24):
            b = bucket_map.get(h)
            if b:
                hourly.append(
                    HourlyAnalytics(
                        camera_id=b.camera_id,
                        date=b.date,
                        hour=b.hour,
                        customer_count=b.customer_count,
                        male_count=b.male_count,
                        female_count=b.female_count,
                        unknown_gender=b.unknown_gender,
                        age_teens=b.age_teens,
                        age_20s=b.age_20s,
                        age_30s=b.age_30s,
                        age_40s=b.age_40s,
                        age_50plus=b.age_50plus,
                        avg_dwell_seconds=b.avg_dwell_seconds or 0.0,
                    )
                )
            else:
                hourly.append(
                    HourlyAnalytics(
                        camera_id=camera_id,
                        date=analytics_date,
                        hour=h,
                    )
                )

        return hourly

    async def get_daily_summary(
        self, camera_id: str, analytics_date: date
    ) -> DailySummary:
        """Get daily summary for a camera.

        Args:
            camera_id: Camera to get summary for.
            analytics_date: Date to get summary for.

        Returns:
            DailySummary with totals, breakdowns, peak hour.
        """
        hourly = await self.get_hourly_breakdown(camera_id, analytics_date)

        summary = DailySummary(
            camera_id=camera_id,
            date=analytics_date,
        )

        peak_count = 0
        total_dwell = 0.0
        hours_with_customers = 0

        for h in hourly:
            summary.total_customers += h.customer_count
            summary.gender_breakdown["male"] += h.male_count
            summary.gender_breakdown["female"] += h.female_count
            summary.gender_breakdown["unknown"] += h.unknown_gender
            summary.age_breakdown["teens"] += h.age_teens
            summary.age_breakdown["20s"] += h.age_20s
            summary.age_breakdown["30s"] += h.age_30s
            summary.age_breakdown["40s"] += h.age_40s
            summary.age_breakdown["50plus"] += h.age_50plus

            if h.customer_count > peak_count:
                peak_count = h.customer_count
                summary.peak_hour = h.hour

            if h.avg_dwell_seconds > 0:
                total_dwell += h.avg_dwell_seconds * h.customer_count
                hours_with_customers += 1

        if summary.total_customers > 0:
            summary.avg_dwell_seconds = total_dwell / summary.total_customers

        # Unique customers and repeat customers require person tracking
        # For now, estimate based on total vs unique from person_sightings
        summary.unique_customers = await self._count_unique_customers(
            camera_id, analytics_date
        )
        summary.repeat_customers = await self._count_repeat_customers(
            camera_id, analytics_date
        )

        return summary

    async def get_peak_hours(
        self, camera_id: str, analytics_date: date
    ) -> list[dict]:
        """Get peak hours sorted by customer count descending.

        Args:
            camera_id: Camera to get peak hours for.
            analytics_date: Date to get peak hours for.

        Returns:
            List of dicts: [{hour: 10, count: 15}, ...]
        """
        hourly = await self.get_hourly_breakdown(camera_id, analytics_date)

        peaks = [
            {"hour": h.hour, "count": h.customer_count}
            for h in hourly
            if h.customer_count > 0
        ]
        peaks.sort(key=lambda x: x["count"], reverse=True)
        return peaks

    async def get_demographic_breakdown(
        self, camera_id: str, analytics_date: date
    ) -> dict:
        """Get demographic breakdown.

        Args:
            camera_id: Camera to get demographics for.
            analytics_date: Date to get demographics for.

        Returns:
            Dict with gender and age breakdowns.
        """
        hourly = await self.get_hourly_breakdown(camera_id, analytics_date)

        gender = {"male": 0, "female": 0, "unknown": 0}
        age = {"teens": 0, "20s": 0, "30s": 0, "40s": 0, "50plus": 0}

        for h in hourly:
            gender["male"] += h.male_count
            gender["female"] += h.female_count
            gender["unknown"] += h.unknown_gender
            age["teens"] += h.age_teens
            age["20s"] += h.age_20s
            age["30s"] += h.age_30s
            age["40s"] += h.age_40s
            age["50plus"] += h.age_50plus

        return {"gender": gender, "age": age}

    async def get_repeat_customers(
        self, camera_id: str, analytics_date: date, min_visits: int = 2
    ) -> list[dict]:
        """Get customers who visited multiple times today.

        CRM tracking: identifies repeat visitors.

        Args:
            camera_id: Camera to check.
            analytics_date: Date to check.
            min_visits: Minimum visits to be considered repeat (default 2).

        Returns:
            List of dicts with person_uid, visit_count, first_seen, last_seen, etc.
        """
        async with self.db_session_factory() as session:
            from backend.storage.database import PersonSighting

            # Get all person sightings for this camera on this date
            result = await session.execute(
                select(PersonSighting)
                .where(
                    and_(
                        PersonSighting.camera_id == camera_id,
                        func.date(PersonSighting.timestamp) == analytics_date,
                    )
                )
                .order_by(PersonSighting.person_uid, PersonSighting.timestamp)
            )
            sightings = list(result.scalars().all())

        # Group by person_uid
        person_visits = defaultdict(list)
        for s in sightings:
            person_visits[s.person_uid].append(s)

        # Filter by min_visits
        repeat_customers = []
        for person_uid, visits in person_visits.items():
            if len(visits) >= min_visits:
                repeat_customers.append(
                    {
                        "person_uid": person_uid,
                        "visit_count": len(visits),
                        "first_seen": visits[0].timestamp.isoformat() if visits[0].timestamp else None,
                        "last_seen": visits[-1].timestamp.isoformat() if visits[-1].timestamp else None,
                        "gender": visits[0].clothing_colors or "unknown",
                        "age_group": "unknown",
                    }
                )

        return repeat_customers

    async def get_weekly_report(
        self, camera_id: str, week_start: date
    ) -> dict:
        """Get weekly analytics report.

        Args:
            camera_id: Camera to get report for.
            week_start: Start date of the week (Monday).

        Returns:
            Dict with weekly aggregated stats.
        """
        week_end = week_start + timedelta(days=6)

        daily_summaries = []
        current = week_start
        while current <= week_end:
            summary = await self.get_daily_summary(camera_id, current)
            daily_summaries.append(summary)
            current += timedelta(days=1)

        total_customers = sum(d.total_customers for d in daily_summaries)
        days_with_data = sum(1 for d in daily_summaries if d.total_customers > 0)

        # Find busiest day
        busiest_day = max(daily_summaries, key=lambda d: d.total_customers) if daily_summaries else None

        # Aggregate gender and age
        gender_avg = {"male": 0, "female": 0, "unknown": 0}
        age_avg = {"teens": 0, "20s": 0, "30s": 0, "40s": 0, "50plus": 0}

        for d in daily_summaries:
            for k in gender_avg:
                gender_avg[k] += d.gender_breakdown.get(k, 0)
            for k in age_avg:
                age_avg[k] += d.age_breakdown.get(k, 0)

        # Average per day
        if days_with_data > 0:
            for k in gender_avg:
                gender_avg[k] = round(gender_avg[k] / days_with_data, 1)
            for k in age_avg:
                age_avg[k] = round(age_avg[k] / days_with_data, 1)

        # Find overall peak hour
        all_peaks = []
        for d in daily_summaries:
            peaks = await self.get_peak_hours(camera_id, d.date)
            if peaks:
                all_peaks.extend(peaks)

        peak_hour = None
        if all_peaks:
            # Aggregate by hour
            hour_counts = defaultdict(int)
            for p in all_peaks:
                hour_counts[p["hour"]] += p["count"]
            peak_hour = max(hour_counts, key=hour_counts.get)

        # Repeat rate
        total_repeat = sum(d.repeat_customers for d in daily_summaries)
        repeat_rate = round(total_repeat / total_customers * 100, 1) if total_customers > 0 else 0.0

        return {
            "total_customers": total_customers,
            "avg_daily": round(total_customers / max(days_with_data, 1), 1),
            "busiest_day": busiest_day.date.isoformat() if busiest_day else None,
            "peak_hour": peak_hour,
            "gender_avg": gender_avg,
            "age_avg": age_avg,
            "repeat_rate": repeat_rate,
        }

    def _is_staff(
        self,
        person_uid: str,
        entrance_zone: str,
        staff_ids: list[str],
        staff_entrance_zones: list[str],
    ) -> bool:
        """Check if person is staff based on Re-ID or entrance zone.

        Args:
            person_uid: Person UID to check.
            entrance_zone: Entrance zone the person came through.
            staff_ids: List of known staff person UIDs.
            staff_entrance_zones: List of staff-only entrance zones.

        Returns:
            True if the person is identified as staff.
        """
        if person_uid in staff_ids:
            return True
        if entrance_zone in staff_entrance_zones:
            return True
        return False

    def _calculate_dwell(
        self, entry: datetime, exit: datetime
    ) -> Optional[float]:
        """Calculate dwell time in seconds.

        Minimum 30s to count. Returns None if below minimum.

        Args:
            entry: Entry timestamp.
            exit: Exit timestamp.

        Returns:
            Dwell time in seconds, or None if below minimum.
        """
        if not entry or not exit:
            return None

        dwell = (exit - entry).total_seconds()
        if dwell < MIN_DWELL_SECONDS:
            return None

        return round(dwell, 1)

    async def _get_visit_count_today(
        self,
        camera_id: str,
        user_id: str,
        person_uid: str,
        analytics_date: date,
    ) -> int:
        """Get the number of visits for a person on a given date.

        Args:
            camera_id: Camera ID.
            user_id: User ID.
            person_uid: Person UID.
            analytics_date: Date to check.

        Returns:
            Visit count for the day.
        """
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import PersonSighting

                result = await session.execute(
                    select(func.count(PersonSighting.id))
                    .where(
                        and_(
                            PersonSighting.person_uid == person_uid,
                            PersonSighting.camera_id == camera_id,
                            func.date(PersonSighting.timestamp) == analytics_date,
                        )
                    )
                )
                return result.scalar() or 1
        except Exception:
            return 1

    async def _count_unique_customers(
        self, camera_id: str, analytics_date: date
    ) -> int:
        """Count unique customers for a camera on a date.

        Args:
            camera_id: Camera ID.
            analytics_date: Date to check.

        Returns:
            Number of unique customers.
        """
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import PersonSighting

                result = await session.execute(
                    select(func.count(func.distinct(PersonSighting.person_uid)))
                    .where(
                        and_(
                            PersonSighting.camera_id == camera_id,
                            func.date(PersonSighting.timestamp) == analytics_date,
                        )
                    )
                )
                return result.scalar() or 0
        except Exception:
            return 0

    async def _count_repeat_customers(
        self, camera_id: str, analytics_date: date
    ) -> int:
        """Count customers who visited more than once on a date.

        Args:
            camera_id: Camera ID.
            analytics_date: Date to check.

        Returns:
            Number of repeat customers.
        """
        try:
            async with self.db_session_factory() as session:
                from backend.storage.database import PersonSighting

                # Subquery: count sightings per person
                subq = (
                    select(
                        PersonSighting.person_uid,
                        func.count(PersonSighting.id).label("visit_count"),
                    )
                    .where(
                        and_(
                            PersonSighting.camera_id == camera_id,
                            func.date(PersonSighting.timestamp) == analytics_date,
                        )
                    )
                    .group_by(PersonSighting.person_uid)
                    .having(func.count(PersonSighting.id) > 1)
                    .subquery()
                )

                result = await session.execute(
                    select(func.count()).select_from(subq)
                )
                return result.scalar() or 0
        except Exception:
            return 0
