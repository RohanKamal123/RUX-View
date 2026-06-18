# Vision OS V8 — DeepSeek Coding Prompts
# Production Deployment & Scaling
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

## SPRINT 10.1 — Auto-Scaling Configuration
### Files: infrastructure/autoscaling.py, infrastructure/cloud_run_config.yaml
### Tests: backend/tests/unit/test_autoscaling.py

```
You are building the auto-scaling configuration for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Google Cloud Run + Python asyncio
- Auto-scales based on: CPU utilization, concurrent requests, queue depth
- Min instances: 1 (keep warm), Max instances: 10 (handle peak)
- Concurrency: 80 requests per instance
- CPU: 2 vCPU, Memory: 2GB per instance
- Startup CPU boost enabled
- Request timeout: 300 seconds (for AI calls)
- Idle timeout: 300 seconds
- VPC connector for Cloud SQL access
- Supports up to 10 cameras per user, scaling for 50+ concurrent users

KEY DECISIONS:
- D026: All calls async
- Cloud Run for serverless scaling
- VPC connector for secure database access

FUNCTIONS TO IMPLEMENT:

1. AutoScalingConfig class:
   - load_config() -> ScalingConfig
   - validate_config(config: ScalingConfig) -> bool
   - generate_cloud_run_yaml(config: ScalingConfig) -> str
   - estimate_cost(instances: int, hours: float) -> CostEstimate
   - get_scaling_recommendations(metrics: dict) -> list[Recommendation]

2. ScalingConfig dataclass:
   - min_instances: int = 1
   - max_instances: int = 10
   - concurrency: int = 80
   - cpu: str = "2"
   - memory: str = "2Gi"
   - startup_cpu_boost: bool = True
   - request_timeout: int = 300
   - idle_timeout: int = 300
   - vpc_connector: Optional[str]
   - vpc_egress: str = "private-ranges-only"

3. CostEstimate dataclass:
   - min_instances: int
   - max_instances: int
   - estimated_monthly_min: float
   - estimated_monthly_max: float
   - estimated_monthly_avg: float
   - cost_per_instance_hour: float
   - assumptions: list[str]

4. Recommendation dataclass:
   - metric: str
   - current_value: float
   - recommended_value: float
   - reason: str
   - estimated_savings: Optional[float]

5. Cloud Run YAML template:
   - Service name: vision-os-api
   - Region: asia-south1 (Mumbai)
   - Container port: 8080
   - Environment variables from Secret Manager
   - Health check: /health endpoint
   - VPC connector for Cloud SQL
   - Cloud Storage for clip storage
   - Secret Manager for API keys

TEST CASES:
test_load_config_returns_defaults, test_validate_config_valid, test_validate_config_invalid_min_instances, test_generate_cloud_run_yaml_contains_required_fields, test_estimate_cost_calculation, test_get_scaling_recommendations_high_cpu, test_get_scaling_recommendations_low_usage, test_config_serialization_deserialization, test_concurrency_limit_enforced

OUTPUT: Generate autoscaling.py, cloud_run_config.yaml, and test_autoscaling.py.
```

---

## SPRINT 10.2 — Load Balancer Setup
### Files: infrastructure/load_balancer.py, infrastructure/load_balancer_config.yaml
### Tests: backend/tests/unit/test_load_balancer.py

```
You are building the load balancer configuration for Vision OS.

CONTEXT:
- Stack: Google Cloud Load Balancer + Cloud Run
- Global HTTPS load balancer with CDN
- SSL certificate auto-provisioning
- URL mapping: /api/* → Cloud Run, /static/* → Cloud Storage
- WebSocket support for real-time camera status
- DDoS protection via Cloud Armor
- Custom domain: visionos.app (or your domain)
- Regional backend: asia-south1

KEY DECISIONS:
- D026: All calls async
- Global LB for low latency across Bangladesh
- Cloud Armor for WAF + DDoS protection

FUNCTIONS TO IMPLEMENT:

1. LoadBalancerConfig class:
   - generate_config(domain: str) -> LBConfig
   - validate_config(config: LBConfig) -> bool
   - generate_url_map(config: LBConfig) -> dict
   - generate_ssl_config(domain: str) -> dict
   - generate_cloud_armor_policy() -> dict
   - estimate_cost(config: LBConfig) -> CostEstimate

2. LBConfig dataclass:
   - domain: str
   - ssl_certificate: str  # managed by Google
   - backend_service: str = "vision-os-backend"
   - static_bucket: str = "vision-os-static"
   - region: str = "asia-south1"
   - enable_cdn: bool = True
   - enable_armor: bool = True
   - websocket_timeout: int = 3600

3. URL Mapping:
   - /api/* → Cloud Run backend
   - /static/* → Cloud Storage bucket
   - /health → Cloud Run (no auth)
   - /login → Cloud Run
   - /admin/* → Cloud Run (admin auth)
   - /ws/* → Cloud Run (WebSocket)
   - /* → Cloud Run (catch-all)

4. Cloud Armor Rules:
   - Rate limiting: 1000 requests/min per IP
   - SQL injection prevention
   - XSS prevention
   - Geographic restriction: allow Bangladesh only (optional)
   - Bot detection

TEST CASES:
test_generate_config_contains_required_fields, test_validate_config_valid, test_generate_url_map_has_all_routes, test_generate_ssl_config, test_generate_cloud_armor_policy, test_estimate_cost, test_websocket_timeout_config, test_cdn_enabled_for_static

OUTPUT: Generate load_balancer.py, load_balancer_config.yaml, and test_load_balancer.py.
```

---

## SPRINT 10.3 — Database Connection Pooling
### Files: backend/storage/connection_pool.py
### Tests: backend/tests/unit/test_connection_pool.py

```
You are building the database connection pooling module for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async + asyncpg + PostgreSQL (Cloud SQL)
- Connection pool management for Cloud SQL
- Pool size: min 2, max 10 connections per instance
- Connection health checks every 30 seconds
- Automatic reconnection on failure
- Query timeout: 30 seconds
- Pool metrics: active connections, idle connections, wait time
- Supports up to 10 cameras per user, 50+ concurrent users
- Read replicas for analytics queries (optional)

KEY DECISIONS:
- D026: All calls async
- SQLAlchemy async with asyncpg driver
- Connection pooling with configurable limits

FUNCTIONS TO IMPLEMENT:

1. ConnectionPoolManager class:
   - initialize_pool(config: PoolConfig) -> asyncpg.Pool
   - get_connection() -> asyncpg.Connection
   - release_connection(conn: asyncpg.Connection) -> None
   - get_pool_stats() -> PoolStats
   - health_check() -> bool
   - reset_pool() -> dict
   - close_pool() -> dict
   - execute_with_retry(query: str, params: tuple, max_retries: int = 3) -> Any
   - execute_in_transaction(queries: list[tuple]) -> list[Any]

2. PoolConfig dataclass:
   - database_url: str
   - min_size: int = 2
   - max_size: int = 10
   - max_queries: int = 50000
   - max_inactive_connection_lifetime: float = 300.0  # seconds
   - command_timeout: int = 30
   - statement_cache_size: int = 100
   - ssl: str = "require"

3. PoolStats dataclass:
   - active_connections: int
   - idle_connections: int
   - total_connections: int
   - max_connections: int
   - waiting_requests: int
   - avg_acquire_time_ms: float
   - total_queries_executed: int
   - queries_per_second: float
   - errors_last_5min: int
   - pool_utilization_pct: float

4. ReadReplicaConfig (optional):
   - enabled: bool = False
   - replica_url: Optional[str]
   - analytics_queries_only: bool = True

TEST CASES:
test_initialize_pool_creates_connections, test_get_connection_returns_valid_conn, test_release_connection_returns_to_pool, test_get_pool_stats_returns_metrics, test_health_check_returns_true, test_reset_pool_recreates_connections, test_close_pool_cleans_up, test_execute_with_retry_succeeds, test_execute_with_retry_fails_after_max, test_execute_in_transaction_commits, test_execute_in_transaction_rolls_back_on_error, test_pool_utilization_calculation, test_connection_timeout_enforced

OUTPUT: Generate connection_pool.py and test_connection_pool.py. Use async/await throughout.
```

---

## SPRINT 10.4 — CDN Integration
### Files: backend/storage/cdn_manager.py
### Tests: backend/tests/unit/test_cdn_manager.py

```
You are building the CDN integration module for Vision OS.

CONTEXT:
- Stack: Python asyncio + Google Cloud Storage + Google Cloud CDN
- Static assets served via CDN (CSS, JS, images)
- Event thumbnails cached on CDN
- Clip playback via CDN for business tier
- Cache invalidation on asset updates
- Signed URLs for private content (thumbnails, clips)
- Cache TTL: 1 hour for static assets, 24 hours for thumbnails
- Supports up to 10 cameras, 1000+ events/day

KEY DECISIONS:
- D026: All calls async
- Google Cloud CDN with Cloud Storage backend
- Signed URLs for private content access

FUNCTIONS TO IMPLEMENT:

1. CDNManager class:
   - upload_static(file_path: str, content_type: str) -> str  # returns CDN URL
   - upload_thumbnail(camera_id: str, event_id: str, image_data: bytes) -> str
   - upload_clip(camera_id: str, event_id: str, clip_data: bytes) -> str
   - get_signed_url(object_path: str, expires_in: int = 3600) -> str
   - invalidate_cache(object_path: str) -> dict
   - invalidate_prefix(prefix: str) -> dict
   - get_cdn_url(object_path: str) -> str
   - delete_object(object_path: str) -> dict
   - list_objects(prefix: str, limit: int = 100) -> list[str]
   - get_storage_usage(prefix: str) -> StorageUsage

2. StorageUsage dataclass:
   - prefix: str
   - total_objects: int
   - total_bytes: int
   - total_mb: float
   - oldest_object: Optional[datetime]
   - newest_object: Optional[datetime]

3. CDN Path Structure:
   - /static/* → Dashboard assets (CSS, JS, images)
   - /thumbnails/{user_id}/{camera_id}/{event_id}.jpg
   - /clips/{user_id}/{camera_id}/{event_id}.mp4
   - /receipts/{user_id}/{payment_id}.pdf

4. Cache TTLs:
   - Static assets: 3600 seconds (1 hour)
   - Thumbnails: 86400 seconds (24 hours)
   - Clips: 0 (no cache, signed URLs)
   - Receipts: 0 (no cache, signed URLs)

TEST CASES:
test_upload_static_returns_cdn_url, test_upload_thumbnail_stores_correctly, test_upload_clip_stores_correctly, test_get_signed_url_generates_valid_url, test_signed_url_expires_after_time, test_invalidate_cache_removes_object, test_invalidate_prefix_removes_multiple, test_get_cdn_url_returns_correct_path, test_delete_object_removes_from_storage, test_list_objects_returns_prefix_matches, test_get_storage_usage_calculates_correctly, test_thumbnail_path_format, test_clip_path_format

OUTPUT: Generate cdn_manager.py and test_cdn_manager.py. Use async/await throughout.
```

---

## SPRINT 10.5 — Monitoring & Alerting
### Files: backend/monitoring/alert_system.py, backend/monitoring/metrics_collector.py
### Tests: backend/tests/unit/test_monitoring.py

```
You are building the monitoring and alerting system for Vision OS.

CONTEXT:
- Stack: Python asyncio + Google Cloud Monitoring + Telegram
- System health monitoring: API latency, error rates, database connections
- Business metrics: active users, cameras, events, revenue
- Alert channels: Telegram (admin group), Email
- Alert thresholds: configurable per metric
- Incident management: auto-create incident on critical alert
- Dashboard: real-time metrics display
- Supports up to 10 cameras per user, monitoring 50+ concurrent users

KEY DECISIONS:
- D026: All calls async
- Telegram admin group for real-time alerts
- Google Cloud Monitoring for infrastructure metrics

FUNCTIONS TO IMPLEMENT:

1. MetricsCollector class:
   - record_api_latency(endpoint: str, latency_ms: float) -> dict
   - record_error(module: str, error_type: str, message: str) -> dict
   - record_business_metric(metric: str, value: float, tags: dict) -> dict
   - get_api_latency_p50(endpoint: str, minutes: int = 5) -> float
   - get_api_latency_p95(endpoint: str, minutes: int = 5) -> float
   - get_error_rate(minutes: int = 5) -> float
   - get_business_metrics(since: datetime) -> BusinessMetrics
   - get_system_health() -> SystemHealth
   - get_realtime_metrics() -> RealtimeMetrics

2. AlertSystem class:
   - check_thresholds() -> list[Alert]
   - send_alert(alert: Alert) -> bool
   - acknowledge_alert(alert_id: str, admin_id: str) -> dict
   - resolve_alert(alert_id: str, admin_id: str) -> dict
   - get_active_alerts() -> list[Alert]
   - get_alert_history(hours: int = 24) -> list[Alert]
   - configure_alert_rule(rule: AlertRule) -> dict
   - silence_alert(alert_id: str, duration_minutes: int) -> dict

3. Alert dataclass:
   - alert_id: str
   - severity: str (info/warning/critical/emergency)
   - metric: str
   - current_value: float
   - threshold_value: float
   - message: str
   - module: str
   - timestamp: datetime
   - status: str (active/acknowledged/resolved/silenced)
   - acknowledged_by: Optional[str]
   - resolved_by: Optional[str]

4. AlertRule dataclass:
   - rule_id: str
   - metric: str
   - condition: str (gt/lt/gte/lte/eq)
   - threshold: float
   - severity: str
   - duration_minutes: int  # sustained for X minutes before alert
   - enabled: bool
   - channels: list[str]  # telegram, email

5. BusinessMetrics dataclass:
   - total_users: int
   - active_users_today: int
   - total_cameras: int
   - online_cameras: int
   - events_today: int
   - high_threat_events: int
   - ai_calls_today: int
   - estimated_revenue_today: float
   - estimated_revenue_monthly: float
   - trial_conversion_rate: float

6. SystemHealth dataclass:
   - status: str (healthy/degraded/unhealthy)
   - api_latency_p95_ms: float
   - error_rate_pct: float
   - database_connections: int
   - database_latency_ms: float
   - active_instances: int
   - cpu_utilization_pct: float
   - memory_utilization_pct: float
   - active_alerts: int

7. RealtimeMetrics dataclass:
   - events_last_minute: int
   - ai_calls_last_minute: int
   - active_websockets: int
   - api_requests_last_minute: int
   - avg_response_time_ms: float
   - error_count_last_minute: int

8. Default Alert Thresholds:
   - API p95 latency > 1000ms → warning
   - API p95 latency > 3000ms → critical
   - Error rate > 5% → warning
   - Error rate > 10% → critical
   - Database connections > 80% → warning
   - Database connections > 95% → critical
   - Offline cameras > 3 per user → warning
   - Offline cameras > 5 per user → critical
   - AI cost > $10/day per user → warning
   - AI cost > $25/day per user → critical

TEST CASES:
test_record_api_latency_stores_metric, test_record_error_creates_entry, test_record_business_metric, test_get_api_latency_p50_p95, test_get_error_rate_calculation, test_get_business_metrics_aggregates, test_get_system_health_returns_status, test_check_thresholds_triggers_alert, test_send_alert_delivers_notification, test_acknowledge_alert_updates_status, test_resolve_alert_clears, test_get_active_alerts_returns_unresolved, test_configure_alert_rule, test_silence_alert_suppresses_notifications, test_realtime_metrics_updates_frequently

OUTPUT: Generate alert_system.py, metrics_collector.py, and test_monitoring.py. Use async/await throughout.
```

---

## Quick Reference: V8 File Paths

| Sprint | File Path |
|--------|-----------|
| 10.1 | `infrastructure/autoscaling.py` |
| 10.1 | `infrastructure/cloud_run_config.yaml` |
| 10.1 | `backend/tests/unit/test_autoscaling.py` |
| 10.2 | `infrastructure/load_balancer.py` |
| 10.2 | `infrastructure/load_balancer_config.yaml` |
| 10.2 | `backend/tests/unit/test_load_balancer.py` |
| 10.3 | `backend/storage/connection_pool.py` |
| 10.3 | `backend/tests/unit/test_connection_pool.py` |
| 10.4 | `backend/storage/cdn_manager.py` |
| 10.4 | `backend/tests/unit/test_cdn_manager.py` |
| 10.5 | `backend/monitoring/alert_system.py` |
| 10.5 | `backend/monitoring/metrics_collector.py` |
| 10.5 | `backend/tests/unit/test_monitoring.py` |

---

*Vision OS V8 — Production Deployment & Scaling*

*Copy, paste, generate, test, commit. Repeat.*
