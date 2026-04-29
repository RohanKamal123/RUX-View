"""
test_onboarding.py — Tests for the User Onboarding Flow.
"""

import pytest
from datetime import datetime, timedelta, timezone
from backend.core.onboarding import (
    OnboardingManager,
    OnboardingSession,
    OnboardingProgress,
    STEP_NAMES,
    TOTAL_STEPS,
)


@pytest.fixture
def manager():
    """Create a fresh OnboardingManager for each test."""
    # Clear the in-memory store
    from backend.core.onboarding import _sessions
    _sessions.clear()
    return OnboardingManager()


@pytest.fixture
def sample_user():
    return "test_user_123"


# ── Test: Start Onboarding ──────────────────────────────────────


@pytest.mark.asyncio
async def test_start_onboarding_creates_session(manager, sample_user):
    session = await manager.start_onboarding(sample_user)

    assert session.user_id == sample_user
    assert session.current_step == 1
    assert session.completed_steps == []
    assert session.skipped_steps == []
    assert session.is_complete is False
    assert session.started_at is not None
    assert session.last_activity is not None


# ── Test: Get Onboarding State ──────────────────────────────────


@pytest.mark.asyncio
async def test_get_onboarding_state_returns_current_step(manager, sample_user):
    await manager.start_onboarding(sample_user)
    session = await manager.get_onboarding_state(sample_user)

    assert session.user_id == sample_user
    assert session.current_step == 1


@pytest.mark.asyncio
async def test_get_onboarding_state_raises_for_missing_user(manager):
    with pytest.raises(ValueError, match="No onboarding session found"):
        await manager.get_onboarding_state("nonexistent_user")


# ── Test: Complete Step ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_step_advances_progress(manager, sample_user):
    await manager.start_onboarding(sample_user)

    session = await manager.complete_step(sample_user, 1, {"email": "test@test.com"})

    assert 1 in session.completed_steps
    assert session.current_step == 2
    assert session.step_data[1] == {"email": "test@test.com"}


@pytest.mark.asyncio
async def test_complete_step_invalid_step(manager, sample_user):
    await manager.start_onboarding(sample_user)

    with pytest.raises(ValueError, match="Invalid step number"):
        await manager.complete_step(sample_user, 99, {})


@pytest.mark.asyncio
async def test_complete_step_last_step_does_not_advance(manager, sample_user):
    await manager.start_onboarding(sample_user)

    # Complete all steps
    for step in range(1, TOTAL_STEPS + 1):
        session = await manager.complete_step(sample_user, step, {"data": f"step_{step}"})

    assert session.current_step == TOTAL_STEPS
    assert len(session.completed_steps) == TOTAL_STEPS


# ── Test: Skip Step ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skip_step_marks_as_skipped(manager, sample_user):
    await manager.start_onboarding(sample_user)

    session = await manager.skip_step(sample_user, 2)

    assert 2 in session.skipped_steps
    assert session.current_step == 3


@pytest.mark.asyncio
async def test_skip_step_invalid_step(manager, sample_user):
    await manager.start_onboarding(sample_user)

    with pytest.raises(ValueError, match="Invalid step number"):
        await manager.skip_step(sample_user, 0)


# ── Test: Go Back Step ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_go_back_step_returns_to_previous(manager, sample_user):
    await manager.start_onboarding(sample_user)
    await manager.complete_step(sample_user, 1, {})

    session = await manager.go_back_step(sample_user, 1)

    assert session.current_step == 1


# ── Test: Complete Onboarding ───────────────────────────────────


@pytest.mark.asyncio
async def test_complete_onboarding_marks_done(manager, sample_user):
    await manager.start_onboarding(sample_user)

    summary = await manager.complete_onboarding(sample_user)

    assert summary["user_id"] == sample_user
    assert "completed_at" in summary

    session = await manager.get_onboarding_state(sample_user)
    assert session.is_complete is True


# ── Test: Is Onboarding Complete ────────────────────────────────


@pytest.mark.asyncio
async def test_is_onboarding_complete_true_after_completion(manager, sample_user):
    await manager.start_onboarding(sample_user)
    await manager.complete_onboarding(sample_user)

    result = await manager.is_onboarding_complete(sample_user)
    assert result is True


@pytest.mark.asyncio
async def test_is_onboarding_complete_false_when_incomplete(manager, sample_user):
    await manager.start_onboarding(sample_user)

    result = await manager.is_onboarding_complete(sample_user)
    assert result is False


@pytest.mark.asyncio
async def test_is_onboarding_complete_false_no_session(manager):
    result = await manager.is_onboarding_complete("nonexistent")
    assert result is False


# ── Test: Onboarding Progress ───────────────────────────────────


@pytest.mark.asyncio
async def test_onboarding_progress_calculation(manager, sample_user):
    await manager.start_onboarding(sample_user)

    # Complete 2 steps, skip 1
    await manager.complete_step(sample_user, 1, {})
    await manager.complete_step(sample_user, 2, {})
    await manager.skip_step(sample_user, 3)

    progress = await manager.get_onboarding_progress(sample_user)

    assert progress.total_steps == TOTAL_STEPS
    assert progress.completed == 2
    assert progress.skipped == 1
    assert progress.remaining == 3
    assert progress.progress_pct == pytest.approx(33.3, abs=0.5)
    assert progress.current_step_name == STEP_NAMES[3]  # Step 4 = "Mode"


@pytest.mark.asyncio
async def test_onboarding_progress_initial(manager, sample_user):
    await manager.start_onboarding(sample_user)

    progress = await manager.get_onboarding_progress(sample_user)

    assert progress.completed == 0
    assert progress.skipped == 0
    assert progress.remaining == TOTAL_STEPS
    assert progress.progress_pct == 0.0
    assert progress.current_step_name == STEP_NAMES[0]  # "Account"


# ── Test: Resume Onboarding ─────────────────────────────────────


@pytest.mark.asyncio
async def test_resume_onboarding_from_saved_state(manager, sample_user):
    await manager.start_onboarding(sample_user)
    await manager.complete_step(sample_user, 1, {"email": "test@test.com"})
    await manager.complete_step(sample_user, 2, {"name": "Home"})

    resumed = await manager.resume_onboarding(sample_user)

    assert resumed.current_step == 3
    assert resumed.step_data[1] == {"email": "test@test.com"}
    assert resumed.step_data[2] == {"name": "Home"}
    assert resumed.last_activity is not None


# ── Test: Step Data Persistence ─────────────────────────────────


@pytest.mark.asyncio
async def test_step_data_persisted_correctly(manager, sample_user):
    await manager.start_onboarding(sample_user)

    account_data = {"email": "user@test.com", "name": "Test User", "phone": "+8801XXXX"}
    await manager.complete_step(sample_user, 1, account_data)

    location_data = {"name": "Office", "address": "Dhaka", "type": "office"}
    await manager.complete_step(sample_user, 2, location_data)

    session = await manager.get_onboarding_state(sample_user)

    assert session.step_data[1] == account_data
    assert session.step_data[2] == location_data


# ── Test: Concurrent Onboarding Sessions ────────────────────────


@pytest.mark.asyncio
async def test_concurrent_onboarding_sessions(manager):
    user_a = "user_a"
    user_b = "user_b"

    session_a = await manager.start_onboarding(user_a)
    session_b = await manager.start_onboarding(user_b)

    assert session_a.user_id == user_a
    assert session_b.user_id == user_b
    assert session_a is not session_b

    # Complete steps independently
    await manager.complete_step(user_a, 1, {"email": "a@test.com"})
    await manager.complete_step(user_b, 1, {"email": "b@test.com"})
    await manager.complete_step(user_a, 2, {"name": "A's Home"})

    state_a = await manager.get_onboarding_state(user_a)
    state_b = await manager.get_onboarding_state(user_b)

    assert state_a.current_step == 3
    assert state_b.current_step == 2


# ── Test: Step Names ────────────────────────────────────────────


def test_step_names_are_correct():
    assert STEP_NAMES == ["Account", "Location", "Camera", "Mode", "Notifications", "Payment"]
    assert TOTAL_STEPS == 6


# ── Test: OnboardingSession Dataclass ───────────────────────────


def test_onboarding_session_defaults():
    session = OnboardingSession(user_id="test")
    assert session.current_step == 1
    assert session.completed_steps == []
    assert session.skipped_steps == []
    assert session.step_data == {}
    assert session.is_complete is False


# ── Test: OnboardingProgress Dataclass ──────────────────────────


def test_onboarding_progress_defaults():
    progress = OnboardingProgress()
    assert progress.total_steps == TOTAL_STEPS
    assert progress.completed == 0
    assert progress.skipped == 0
    assert progress.remaining == TOTAL_STEPS
    assert progress.progress_pct == 0.0
    assert progress.current_step_name == STEP_NAMES[0]
