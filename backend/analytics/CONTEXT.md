# CONTEXT.md — Analytics Module
# Module: backend/analytics/
# Sprint: 4.2 (shop_analytics), 4.3 (digest_generator), 5.4 (report_builder)
# Purpose: Business intelligence + user digests

---

## What This Module Does

Three files:

1. **shop_analytics.py** — Customer counting, demographics, peak hours (Business tier)
2. **digest_generator.py** — Daily + weekly Telegram digests per tier
3. **report_builder.py** — Business reports (weekly PDF)

---

## File: shop_analytics.py

### Functions
```python
async def record_customer_entry(camera_id: str, gemma_result: dict) -> None
    # Records: gender, age_group, timestamp, dwell time

async def aggregate_hourly(camera_id: str, date: date) -> None
    # Aggregates into shop_analytics table

async def get_daily_summary(camera_id: str, date: date) -> dict
    # Returns: {total_customers, gender_breakdown, age_breakdown, peak_hours, avg_dwell}

async def get_peak_hours(camera_id: str, date: date) -> list
    # Returns: [{hour: 14, count: 23}, ...]

async def get_demographic_breakdown(camera_id: str, date: date) -> dict
    # Returns: {male_pct, female_pct, teens_pct, 20s_pct, ...}
```

### Staff Filtering
- Staff identified via Re-ID match to labelled profiles
- OR entering via staff entrance zone
- OR arriving before shop opens
- Staff excluded from customer counts

---

## File: digest_generator.py

### Functions
```python
async def generate_daily_digest(user_id: str, date: date, tier: str) -> str
    # Free: short Telegram message (<200 words)
    # Household: detailed + person stats
    # Business: + shop analytics

async def generate_weekly_digest(user_id: str, week_start: date, tier: str) -> str
    # Similar but weekly aggregation
```

### Scheduling (APScheduler)
- Daily: cron at 22:00 user local time
- Weekly: cron Monday 08:00
- AsyncIOScheduler in FastAPI lifespan

### Key Decisions
- **D024** — APScheduler (NOT `schedule` library)
- **D014** — Free tier gets digest (conversion hook)

---

## File: report_builder.py

### Functions
```python
async def build_weekly_report(user_id: str, week_start: date) -> bytes
    # Returns: PDF bytes for download
```

## Dependencies
- backend/ai/ai_client.py (digest generation)
- backend/storage/database.py (event queries)
- backend/alerts/telegram_client.py (sending)

## Called By
- APScheduler jobs (registered in dashboard/server.py)
