"""
incident_builder.py — Incident management and Gemini trigger decisions.

Decides when to call Gemini based on track state changes.
Core cost-control logic: Gemini only runs when something
meaningfully changes — new track, threat escalation, or
periodic update every 120s.

Decision rules:
  CALL Gemini: new track appeared
  CALL Gemini: no Gemini call in last 120s (periodic update)
  CALL Gemini: track count changed significantly (±2)
  SKIP:        same tracks, called Gemini within 120s
  SKIP:        change_detected=False returned by Gemini
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

GEMINI_INTERVAL_SEC = 60
_last_gemini_call: dict[str, float] = {}
_last_track_count: dict[str, int] = {}


@dataclass
class IncidentDecision:
    should_call_gemini: bool
    reason: str
    enriched_prompt_context: str = ""


def should_call_gemini(
    camera_id: str,
    tracking_result,  # TrackingResult from botsort_tracker
    config: Optional[dict] = None,
) -> IncidentDecision:
    """Decide whether this frame warrants a Gemini call.

    Args:
        camera_id: Camera identifier for state lookup.
        tracking_result: TrackingResult from botsort_tracker.
        config: Optional runtime config dict (e.g. from config_store).
                ``gemini_interval_sec`` and ``track_count_delta``
                are read from it.

    Returns:
        IncidentDecision with should_call_gemini and reason.
    """
    gemini_interval = (
        config.get("gemini_interval_sec", 60) if config else GEMINI_INTERVAL_SEC
    )
    track_delta = (
        config.get("track_count_delta", 2) if config else 2
    )

    now = time.time()
    last_call = _last_gemini_call.get(camera_id, 0)
    last_count = _last_track_count.get(camera_id, 0)
    current_count = len(tracking_result.tracks)

    # Rule 1: New track appeared
    if tracking_result.new_tracks:
        new_names = [t.class_name for t in tracking_result.new_tracks]
        _update_state(camera_id, now, current_count)
        return IncidentDecision(
            should_call_gemini=True,
            reason=f"New object detected: {', '.join(new_names)}",
            enriched_prompt_context=_build_context(tracking_result),
        )

    # Rule 2: Periodic update (gemini_interval_sec interval)
    if tracking_result.tracks and (now - last_call) >= gemini_interval:
        _update_state(camera_id, now, current_count)
        if last_call == 0:
            # Throttle was reset — first Gemini call for this session
            reason = "first call for this session"
        else:
            reason = f"Periodic update ({int(now - last_call)}s since last call)"
        return IncidentDecision(
            should_call_gemini=True,
            reason=reason,
            enriched_prompt_context=_build_context(tracking_result),
        )

    # Rule 3: Track count changed significantly
    if abs(current_count - last_count) >= track_delta:
        _update_state(camera_id, now, current_count)
        return IncidentDecision(
            should_call_gemini=True,
            reason=f"Track count changed: {last_count} → {current_count}",
            enriched_prompt_context=_build_context(tracking_result),
        )

    # Default: skip
    return IncidentDecision(
        should_call_gemini=False,
        reason="No significant change detected",
    )


def reset_gemini_throttle(camera_id: str) -> None:
    """Reset per-camera Gemini throttle on session close.
    
    When a session ends, pop the last_call timestamp so that
    a new session on the same camera immediately gets a Gemini
    evaluation instead of being throttled by the old session's
    call history.
    """
    _last_gemini_call.pop(camera_id, None)
    _last_track_count.pop(camera_id, None)
    logger.debug("Gemini throttle reset for camera %s", camera_id)


def cleanup_synthetic_camera(camera_id: str) -> None:
    """Remove all module-level state for a synthetic (clip-analysis) camera.

    # REQUIRED CALLER PATTERN (see clip_analysis.py once built):
    #
    #     synthetic_id = f"clip-analysis-{clip_id}"
    #     try:
    #         for frame in frames:
    #             result = await pv2.process_frame(
    #                 camera_id=synthetic_id, dry_run=True, ...)
    #     finally:
    #         cleanup_synthetic_camera(synthetic_id)
    #         pipeline_manager.cleanup_synthetic_camera(synthetic_id)
    #
    # This MUST run even if the clip loop crashes partway
    # through (bad frame, OOM, timeout) or synthetic camera
    # state leaks indefinitely across a week of repeated
    # clip-analysis runs.
    
    Called after a clip analysis run completes (success or failure)
    to prevent synthetic camera entries from accumulating in
    _last_gemini_call and _last_track_count.
    """
    _last_gemini_call.pop(camera_id, None)
    _last_track_count.pop(camera_id, None)
    logger.debug("Cleaned up synthetic camera %s from incident_builder", camera_id)


def record_no_change(camera_id: str) -> None:
    """Called when Gemini returns change_detected=False.
    Extends the skip window — no need to call again soon.
    """
    _last_gemini_call[camera_id] = time.time()
    logger.debug("NO_CHANGE recorded for %s — extending skip window", camera_id)


def _update_state(camera_id: str, now: float, count: int) -> None:
    _last_gemini_call[camera_id] = now
    _last_track_count[camera_id] = count


def _build_context(tracking_result) -> str:
    """Build enriched context string to prepend to Gemini prompt."""
    lines = ["AI vision system detected:"]
    for track in tracking_result.tracks:
        duration = int(time.time() - track.first_seen)
        status = "NEW" if track.is_new else f"present {duration}s"
        lines.append(f"  {track.class_name} [{track.track_id}]: {status}")
    return "\n".join(lines)