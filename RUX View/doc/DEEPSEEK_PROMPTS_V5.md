# Vision OS V5 — DeepSeek Coding Prompts
# Copy-paste these prompts into DeepSeek to generate each sprint's code
# Each prompt includes: context + function signatures + test cases

---

## How to Use

1. Open DeepSeek (chat.deepseek.com)
2. Copy the entire prompt block for the sprint you want
3. Paste into DeepSeek
4. DeepSeek will generate: code + tests + docstring
5. Save the generated files to the correct paths
6. Run `pytest` to verify tests pass
7. Commit with `git commit -m "feat: [module] what it does"`

---

## SPRINT 7.1 — iOS Viewer App (Swift)
### Files: ios/VisionOS/... (multiple Swift files)
### Tests: ios/VisionOSTests/... (unit tests)

```
You are building the iOS viewer app for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Swift + SwiftUI + Alamofire + Firebase Auth + APNs + Kingfisher
- Thin client ONLY — no processing, no AI, no audio capture
- All intelligence runs on backend — this is a viewer/notification app
- Users receive push notifications for HIGH/EMERGENCY alerts
- Tap notification → opens event detail in app
- Firebase Auth for login (same as dashboard — D012)
- Follows iOS HIG (Human Interface Guidelines)
- Dark mode support (matches dashboard dark navy theme)

KEY DECISIONS:
- D012: Firebase Auth (NOT custom auth)
- D014: Three pricing tiers (free/household/business)
- iOS V5 (Android was V4 Sprint 6.1)

SCREENS TO BUILD:

1. LoginView.swift
2. CameraListView.swift
3. EventFeedView.swift
4. EventDetailView.swift
5. PersonProfileView.swift
6. SettingsView.swift
7. AppDelegate.swift (APNs)
8. VisionOSApiService.swift
9. VisionOSTests.swift

OUTPUT: Generate all Swift files for the iOS app. Use SwiftUI throughout.
```

---

## SPRINT 7.2 — Performance Optimization + Caching
### Files: backend/core/cache_manager.py, backend/core/rate_limiter.py, backend/core/query_optimizer.py
### Tests: backend/tests/unit/test_performance.py

```
You are building the performance optimization and caching modules for Vision OS.

CONTEXT:
- Stack: Python asyncio + Redis (optional) + SQLAlchemy async
- In-memory LRU cache for frequently accessed data
- Redis for distributed caching when available (falls back to in-memory)
- Rate limiting per user/camera for API endpoints
- Query optimization: materialized views for analytics aggregations
- Connection pooling tuned for Cloud Run 2-vCPU instances

KEY DECISIONS:
- D026: All calls async
- Redis optional: degrade gracefully to in-memory cache

FUNCTIONS TO IMPLEMENT:
- cache_manager.py: LRUCache, CacheManager classes
- rate_limiter.py: RateLimiter class with sliding window counter
- query_optimizer.py: QueryOptimizer class with materialized views

PERFORMANCE TARGETS:
- API Response Times (p95): Event list <200ms, Event detail <150ms, Camera list <100ms, Person profile <300ms, Analytics <500ms, Health check <100ms
- Cache Hit Ratios: Camera list >95%, Event list >80%, Person profile >70%, Settings >99%
- Rate Limits: API 60/min, Events 120/min, Analytics 30/min, Admin 120/min

TEST CASES:
test_lru_cache_hit_returns_value, test_lru_cache_miss_returns_none, test_lru_cache_evicts_oldest_when_full, test_cache_ttl_expires_entries, test_cache_manager_compute_on_miss, test_rate_limiter_allows_within_limit, test_rate_limiter_blocks_excess, test_query_optimizer_adds_pagination, test_materialized_view_refresh, test_cache_warm_for_new_user

OUTPUT: Generate cache_manager.py, rate_limiter.py, query_optimizer.py, and test_performance.py. Use async/await throughout.
```

---

## SPRINT 7.3 — Advanced Analytics + Reporting
### Files: backend/analytics/advanced_analytics.py, backend/analytics/trend_analyzer.py, backend/analytics/anomaly_detector.py
### Tests: backend/tests/unit/test_advanced_analytics.py

```
You are building the advanced analytics and trend analysis modules for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + numpy + scipy (optional)
- Business tier feature: trend analysis, anomaly detection, predictive insights
- Weekly/monthly trend reports with visual data
- Anomaly detection: statistical deviation from historical baseline
- Predictive insights: "Based on trends, tomorrow's peak hour will be 10-11am"
- All data from existing shop_analytics and events tables

KEY DECISIONS:
- D014: Advanced analytics exclusive to Business tier
- D026: All calls async

FUNCTIONS TO IMPLEMENT:
- advanced_analytics.py: AdvancedAnalytics class with WeeklyReport, MonthlyReport, TrendAnalysis dataclasses
- trend_analyzer.py: TrendAnalyzer class with event/person/audio trend analysis
- anomaly_detector.py: AnomalyDetector class with statistical anomaly detection

TEST CASES:
test_weekly_report_generates_all_sections, test_monthly_report_includes_trends, test_customer_trend_detection_rising, test_customer_trend_detection_falling, test_peak_hour_prediction_returns_reasonable_hour, test_customer_retention_calculation, test_event_anomaly_detection_above_threshold, test_event_anomaly_no_detection_within_normal, test_baseline_builds_hourly_pattern, test_trend_analyzer_moving_average

OUTPUT: Generate advanced_analytics.py, trend_analyzer.py, anomaly_detector.py, and test_advanced_analytics.py. Use async/await throughout.
```

---

## SPRINT 7.4 — Multi-Camera Recording + Clip Playback
### Files: backend/storage/clip_recorder.py, backend/storage/clip_player.py, backend/api/clips.py
### Tests: backend/tests/unit/test_clips.py

```
You are building the clip recording and playback module for Vision OS.

CONTEXT:
- Stack: Python asyncio + ffmpeg + SQLAlchemy async + Google Cloud Storage
- Record short video clips around triggered events (not continuous recording)
- Clip duration: 10s before trigger + 20s after = 30s total
- Clips stored in Google Cloud Storage (not local)
- Thumbnail extracted from clip midpoint for dashboard display
- Clip retention matches event retention (7/30/90 days by tier)
- Bandwidth-efficient: only record when trigger fires

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming) — clips are trigger-based
- D006: No video recording in V1 — this adds clip recording in V5
- D014: Clip playback: free=no clips, household=30s clips, business=60s clips

FUNCTIONS TO IMPLEMENT:
- clip_recorder.py: ClipRecorder class with record_clip, extract_thumbnail, upload_to_storage
- clip_player.py: ClipPlayer class with get_clip_url, stream_clip, tier access checks
- clips.py: FastAPI router with endpoints for event clips, play, thumbnail, record

TEST CASES:
test_clip_recording_creates_valid_mp4, test_clip_thumbnail_extracted_from_midpoint, test_clip_uploaded_to_cloud_storage, test_clip_metadata_saved_to_database, test_free_tier_no_clip_access, test_household_tier_30s_clips, test_business_tier_60s_clips, test_clip_streaming_with_byte_range, test_get_clips_for_event_returns_all, test_cleanup_temp_files_after_upload

OUTPUT: Generate clip_recorder.py, clip_player.py, clips.py, and test_clips.py. Use async/await throughout.
```

---

## SPRINT 7.5 — Multi-Language Support (i18n)
### Files: backend/i18n/translations.py, backend/i18n/locales/bn.json, backend/i18n/locales/en.json
### Tests: backend/tests/unit/test_i18n.py

```
You are building the internationalization (i18n) module for Vision OS.

CONTEXT:
- Stack: Python asyncio + JSON translation files
- Primary languages: English (en), Bangla (bn)
- All user-facing strings externalized to translation files
- Dashboard templates use Jinja2 i18n extension
- Telegram alerts support language preference per user
- Digest text generated in user's preferred language
- Bangla support critical for Bangladesh market adoption

KEY DECISIONS:
- D026: All calls async
- Bangla (bn) as primary local language
- English (en) as fallback

FUNCTIONS TO IMPLEMENT:
- translations.py: TranslationService, Jinja2I18nExtension, TelegramTranslator classes
- en.json: English translation file with all UI strings
- bn.json: Bangla translation file with all UI strings

TEST CASES:
test_translate_english_returns_correct_string, test_translate_bangla_returns_correct_string, test_translate_fallback_to_english_when_missing, test_translate_with_format_parameters, test_user_language_persisted_in_settings, test_jinja2_translate_filter_works, test_telegram_alert_formatted_in_bangla, test_digest_formatted_in_user_language, test_load_translations_from_file, test_reload_all_translations

OUTPUT: Generate translations.py, en.json, bn.json, and test_i18n.py. Use async/await throughout.
```

---

## Quick Reference: V5 File Paths

| Sprint | File Path |
|--------|-----------|
| 7.1 | `ios/VisionOS/Views/LoginView.swift` |
| 7.1 | `ios/VisionOS/Views/CameraListView.swift` |
| 7.1 | `ios/VisionOS/Views/EventFeedView.swift` |
| 7.1 | `ios/VisionOS/Views/EventDetailView.swift` |
| 7.1 | `ios/VisionOS/Views/PersonProfileView.swift` |
| 7.1 | `ios/VisionOS/Views/SettingsView.swift` |
| 7.1 | `ios/VisionOS/Services/AppDelegate.swift` |
| 7.1 | `ios/VisionOS/Services/VisionOSApiService.swift` |
| 7.1 | `ios/VisionOSTests/VisionOSTests.swift` |
| 7.2 | `backend/core/cache_manager.py` |
| 7.2 | `backend/core/rate_limiter.py` |
| 7.2 | `backend/core/query_optimizer.py` |
| 7.2 | `backend/tests/unit/test_performance.py` |
| 7.3 | `backend/analytics/advanced_analytics.py` |
| 7.3 | `backend/analytics/trend_analyzer.py` |
| 7.3 | `backend/analytics/anomaly_detector.py` |
| 7.3 | `backend/tests/unit/test_advanced_analytics.py` |
| 7.4 | `backend/storage/clip_recorder.py` |
| 7.4 | `backend/storage/clip_player.py` |
| 7.4 | `backend/api/clips.py` |
| 7.4 | `backend/tests/unit/test_clips.py` |
| 7.5 | `backend/i18n/translations.py` |
| 7.5 | `backend/i18n/locales/en.json` |
| 7.5 | `backend/i18n/locales/bn.json` |
| 7.5 | `backend/tests/unit/test_i18n.py` |

---

*Vision OS V5 — DeepSeek Coding Prompts*

*Copy, paste, generate, test, commit. Repeat.*
