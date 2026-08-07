"""Tests that the three documented-but-never-wired scheduled jobs (daily
digest, weekly digest, retention cleanup) actually get registered on app
startup.

Before this, apscheduler was a declared dependency and multiple docs
(including CLAUDE.md) described these jobs as running -- none of that was
true. server.py's lifespan never created a scheduler, DataCleanup and
DigestGenerator were never instantiated anywhere, and DataCleanup's own
deletion methods were TODO stubs that always returned 0. See
backend/dashboard/server.py and backend/storage/cleanup.py.
"""

import pytest
from fastapi.testclient import TestClient

import backend.dashboard.server as server_module
from backend.dashboard.server import app


def test_scheduler_starts_with_all_jobs():
    with TestClient(app):
        scheduler = server_module.scheduler
        assert scheduler is not None
        assert scheduler.running

        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {
            "daily_retention_cleanup", "daily_digest", "weekly_digest",
            "db_pool_config_refresh",
        }


def test_db_pool_config_refresh_runs_every_5_minutes():
    """The multi-instance fallback path for db_pool_* config changes --
    the primary path is the immediate refresh_engine_config() call from
    POST /api/config/thresholds (see test_client_config_api.py), this job
    catches instances that didn't handle that particular write."""
    with TestClient(app):
        job = server_module.scheduler.get_job("db_pool_config_refresh")
        assert job.trigger.interval.total_seconds() == 5 * 60


def test_daily_retention_cleanup_runs_at_3am():
    with TestClient(app):
        job = server_module.scheduler.get_job("daily_retention_cleanup")
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["hour"] == "3"
        assert fields["minute"] == "0"


def test_daily_digest_runs_at_10pm():
    with TestClient(app):
        job = server_module.scheduler.get_job("daily_digest")
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["hour"] == "22"
        assert fields["minute"] == "0"


def test_weekly_digest_runs_monday_8am():
    with TestClient(app):
        job = server_module.scheduler.get_job("weekly_digest")
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["day_of_week"] == "mon"
        assert fields["hour"] == "8"


def test_data_cleanup_and_digest_generator_are_real_instances():
    """app.state should hold real, usable instances, not None/placeholders --
    confirms the scheduler jobs have something real to call, not a
    construction failure that got silently swallowed."""
    with TestClient(app) as client:
        assert client.app.state.data_cleanup is not None
        assert client.app.state.digest_generator is not None
        # DataCleanup's deletion methods must be implemented, not the old
        # `return 0` stubs -- exercised for real in test_cleanup.py, this
        # just confirms the instance handed to the scheduler is wired up
        # the same way (real db_session_factory, not a placeholder).
        assert client.app.state.data_cleanup.db_session_factory is not None


def test_scheduler_shuts_down_cleanly():
    with TestClient(app):
        scheduler = server_module.scheduler
        assert scheduler.running
    # After the TestClient context exits, lifespan shutdown has run.
    assert not scheduler.running
