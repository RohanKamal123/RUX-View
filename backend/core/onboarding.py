"""
onboarding.py — User Onboarding Flow for Vision OS.

Multi-step onboarding wizard for new users:
1) Account creation, 2) Location setup, 3) Camera connection,
4) Mode selection, 5) Notification config, 6) Payment setup

Key decisions:
- D012: Firebase Auth for login
- D026: All calls async
- Onboarding progress saved to database (can resume)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Step Names ──────────────────────────────────────────────────

STEP_NAMES = [
    "Account",
    "Location",
    "Camera",
    "Mode",
    "Notifications",
    "Payment",
]

TOTAL_STEPS = len(STEP_NAMES)  # 6


# ── Dataclasses ─────────────────────────────────────────────────


@dataclass
class OnboardingSession:
    """Represents a user's onboarding session."""

    user_id: str
    current_step: int = 1  # 1-6
    completed_steps: list[int] = field(default_factory=list)
    skipped_steps: list[int] = field(default_factory=list)
    step_data: dict[int, dict] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_complete: bool = False


@dataclass
class OnboardingProgress:
    """Progress summary for the onboarding wizard."""

    total_steps: int = TOTAL_STEPS
    completed: int = 0
    skipped: int = 0
    remaining: int = TOTAL_STEPS
    progress_pct: float = 0.0
    current_step_name: str = STEP_NAMES[0]


# ── In-Memory Store (replace with DB in production) ────────────

_sessions: dict[str, OnboardingSession] = {}


# ── OnboardingManager ───────────────────────────────────────────


class OnboardingManager:
    """Manages the multi-step user onboarding flow."""

    async def start_onboarding(self, user_id: str) -> OnboardingSession:
        """Start a new onboarding session for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            A new OnboardingSession starting at step 1.
        """
        if user_id in _sessions:
            logger.warning("Onboarding already started for user: %s", user_id)
            return _sessions[user_id]

        session = OnboardingSession(user_id=user_id)
        _sessions[user_id] = session
        logger.info("Onboarding started for user: %s", user_id)
        return session

    async def get_onboarding_state(self, user_id: str) -> OnboardingSession:
        """Get the current onboarding state for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            Current OnboardingSession.

        Raises:
            ValueError: If no session exists for the user.
        """
        if user_id not in _sessions:
            raise ValueError(f"No onboarding session found for user: {user_id}")
        session = _sessions[user_id]
        session.last_activity = datetime.now(timezone.utc)
        return session

    async def complete_step(
        self, user_id: str, step: int, data: dict
    ) -> OnboardingSession:
        """Mark a step as completed and save its data.

        Args:
            user_id: Unique user identifier.
            step: Step number (1-6) to complete.
            data: Data collected for this step.

        Returns:
            Updated OnboardingSession.

        Raises:
            ValueError: If step is invalid or session not found.
        """
        if step < 1 or step > TOTAL_STEPS:
            raise ValueError(f"Invalid step number: {step}. Must be 1-{TOTAL_STEPS}.")

        session = await self.get_onboarding_state(user_id)

        if step not in session.completed_steps:
            session.completed_steps.append(step)

        # Remove from skipped if previously skipped
        if step in session.skipped_steps:
            session.skipped_steps.remove(step)

        session.step_data[step] = data
        session.last_activity = datetime.now(timezone.utc)

        # Advance to next step if not the last
        if step < TOTAL_STEPS:
            session.current_step = step + 1
        else:
            session.current_step = step

        logger.info(
            "Step %d completed for user: %s. Current step: %d",
            step, user_id, session.current_step,
        )
        return session

    async def skip_step(self, user_id: str, step: int) -> OnboardingSession:
        """Skip a step (user can configure later).

        Args:
            user_id: Unique user identifier.
            step: Step number (1-6) to skip.

        Returns:
            Updated OnboardingSession.

        Raises:
            ValueError: If step is invalid or session not found.
        """
        if step < 1 or step > TOTAL_STEPS:
            raise ValueError(f"Invalid step number: {step}. Must be 1-{TOTAL_STEPS}.")

        session = await self.get_onboarding_state(user_id)

        if step not in session.skipped_steps:
            session.skipped_steps.append(step)

        session.last_activity = datetime.now(timezone.utc)

        # Advance to next step if not the last
        if step < TOTAL_STEPS:
            session.current_step = step + 1
        else:
            session.current_step = step

        logger.info(
            "Step %d skipped for user: %s. Current step: %d",
            step, user_id, session.current_step,
        )
        return session

    async def go_back_step(self, user_id: str, step: int) -> OnboardingSession:
        """Go back to a previous step.

        Args:
            user_id: Unique user identifier.
            step: Step number (1-6) to go back to.

        Returns:
            Updated OnboardingSession.

        Raises:
            ValueError: If step is invalid or session not found.
        """
        if step < 1 or step > TOTAL_STEPS:
            raise ValueError(f"Invalid step number: {step}. Must be 1-{TOTAL_STEPS}.")

        session = await self.get_onboarding_state(user_id)
        session.current_step = step
        session.last_activity = datetime.now(timezone.utc)

        logger.info(
            "User %s went back to step %d", user_id, step
        )
        return session

    async def complete_onboarding(self, user_id: str) -> dict:
        """Mark onboarding as complete for a user.

        Args:
            user_id: Unique user identifier.

        Returns:
            Summary dict with completion info.

        Raises:
            ValueError: If session not found.
        """
        session = await self.get_onboarding_state(user_id)
        session.is_complete = True
        session.last_activity = datetime.now(timezone.utc)

        summary = {
            "user_id": user_id,
            "completed_steps": session.completed_steps,
            "skipped_steps": session.skipped_steps,
            "completed_at": session.last_activity.isoformat(),
            "total_steps_completed": len(session.completed_steps),
        }

        logger.info("Onboarding completed for user: %s", user_id)
        return summary

    async def is_onboarding_complete(self, user_id: str) -> bool:
        """Check if a user has completed onboarding.

        Args:
            user_id: Unique user identifier.

        Returns:
            True if onboarding is complete, False otherwise.
        """
        try:
            session = await self.get_onboarding_state(user_id)
            return session.is_complete
        except ValueError:
            return False

    async def get_onboarding_progress(self, user_id: str) -> OnboardingProgress:
        """Get detailed progress of the onboarding flow.

        Args:
            user_id: Unique user identifier.

        Returns:
            OnboardingProgress with completion stats.

        Raises:
            ValueError: If session not found.
        """
        session = await self.get_onboarding_state(user_id)
        completed = len(session.completed_steps)
        skipped = len(session.skipped_steps)
        remaining = TOTAL_STEPS - completed - skipped
        if remaining < 0:
            remaining = 0
        progress_pct = (completed / TOTAL_STEPS) * 100 if TOTAL_STEPS > 0 else 0.0

        current_step_name = STEP_NAMES[session.current_step - 1]

        return OnboardingProgress(
            total_steps=TOTAL_STEPS,
            completed=completed,
            skipped=skipped,
            remaining=remaining,
            progress_pct=round(progress_pct, 1),
            current_step_name=current_step_name,
        )

    async def resume_onboarding(self, user_id: str) -> OnboardingSession:
        """Resume onboarding from saved state.

        Args:
            user_id: Unique user identifier.

        Returns:
            Current OnboardingSession ready to continue.

        Raises:
            ValueError: If no session exists.
        """
        session = await self.get_onboarding_state(user_id)
        session.last_activity = datetime.now(timezone.utc)
        logger.info(
            "Onboarding resumed for user: %s at step %d",
            user_id, session.current_step,
        )
        return session
