"""
botsort_tracker.py — Stateful BoT-SORT tracker with Redis persistence.

Assigns persistent Track IDs to detected persons per camera.
State is stored in Upstash Redis so track continuity survives
across Cloud Run invocations (stateless container).

Track state per camera stored as Redis hash:
  key: "track:{camera_id}"
  fields: track_id → JSON {first_seen, last_seen, frame_count,
                            class_name, bbox_last}
TTL: 300 seconds (5 minutes — matches SESSION_TIMEOUT_SEC)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

TRACK_TTL_SECONDS = 300


@dataclass
class Track:
    track_id: str
    class_name: str
    confidence: float
    bbox: list[float]
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    frame_count: int = 1
    is_new: bool = True  # True on first appearance this session


@dataclass
class TrackingResult:
    tracks: list[Track] = field(default_factory=list)
    new_tracks: list[Track] = field(default_factory=list)
    lost_tracks: list[str] = field(default_factory=list)
    track_summary: str = ""


async def update_tracks(
    camera_id: str,
    detections,  # list[Detection] from yolo_detector
    redis_client,
    config: Optional[dict] = None,
    dry_run: bool = False,
) -> TrackingResult:
    """Update track state for a camera based on new detections.

    Loads existing tracks from Redis, matches detections to tracks
    by IoU overlap, creates new tracks for unmatched detections,
    and persists updated state back to Redis (unless dry_run=True).

    Args:
        camera_id: Unique camera identifier.
        detections: List of Detection objects from yolo_detector.
        redis_client: Upstash async Redis client instance.
        config: Optional runtime config dict (e.g. from config_store).
                ``track_match_iou`` is read from it.
        dry_run: If True, suppress Redis writes (track state is not
                 persisted).  Track matching and result building still
                 happen in memory.

    Returns:
        TrackingResult with current tracks, new tracks, and summary.
    """
    redis_key = f"track:{camera_id}"

    # Load existing tracks from Redis
    existing_raw = {}
    try:
        existing_raw = await redis_client.hgetall(redis_key) or {}
    except Exception as e:
        logger.warning("Redis read failed for %s: %s", camera_id, e)

    existing_tracks: dict[str, dict] = {}
    for tid, raw in existing_raw.items():
        try:
            existing_tracks[tid] = json.loads(raw)
        except Exception:
            pass

    match_iou = config.get("track_match_iou", 0.25) if config else 0.25
    lost_threshold = config.get("lost_track_threshold_sec", 30) if config else 30
    track_ttl = config.get("track_ttl_sec", TRACK_TTL_SECONDS) if config else TRACK_TTL_SECONDS
    now = time.time()
    matched_track_ids = set()
    result_tracks = []
    new_tracks = []

    for det in detections:
        matched_id = _match_detection_to_track(det, existing_tracks, match_iou=match_iou)

        if matched_id:
            # Update existing track
            matched_track_ids.add(matched_id)
            t = existing_tracks[matched_id]
            t["last_seen"] = now
            t["frame_count"] = t.get("frame_count", 1) + 1
            t["bbox_last"] = det.bbox
            track = Track(
                track_id=matched_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                first_seen=t["first_seen"],
                last_seen=now,
                frame_count=t["frame_count"],
                is_new=False,
            )
        else:
            # New track — mint a new ID
            new_id = _mint_track_id(camera_id, existing_tracks)
            existing_tracks[new_id] = {
                "first_seen": now,
                "last_seen": now,
                "frame_count": 1,
                "class_name": det.class_name,
                "bbox_last": det.bbox,
            }
            matched_track_ids.add(new_id)
            track = Track(
                track_id=new_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                is_new=True,
            )
            new_tracks.append(track)

        result_tracks.append(track)

    # Tracks not seen this frame — check if lost
    lost_tracks = [
        tid for tid in existing_tracks
        if tid not in matched_track_ids
        and (now - existing_tracks[tid].get("last_seen", now)) > lost_threshold
    ]
    for tid in lost_tracks:
        existing_tracks.pop(tid, None)

    # Persist updated state to Redis (skip on dry_run)
    if not dry_run:
        try:
            if existing_tracks:
                pipe_data = {
                    tid: json.dumps(state)
                    for tid, state in existing_tracks.items()
                }
                for field, value in pipe_data.items():
                    await redis_client.hset(redis_key, field, value)
                await redis_client.expire(redis_key, track_ttl)
            else:
                await redis_client.delete(redis_key)
        except Exception as e:
            logger.warning("Redis write failed for %s: %s", camera_id, e)
    else:
        logger.debug("Dry run: skipped Redis persist for %s (would write %d tracks)", camera_id, len(existing_tracks))

    # Build human-readable track summary for Gemini context
    summary_parts = []
    for t in result_tracks:
        duration = int(now - t.first_seen)
        if t.is_new:
            summary_parts.append(f"New {t.class_name} {t.track_id} appeared")
        else:
            summary_parts.append(
                f"{t.class_name} {t.track_id} present "
                f"{duration}s ({t.frame_count} frames)"
            )
    track_summary = "; ".join(summary_parts) if summary_parts else "No tracked objects"

    return TrackingResult(
        tracks=result_tracks,
        new_tracks=new_tracks,
        lost_tracks=lost_tracks,
        track_summary=track_summary,
    )


def _match_detection_to_track(
    detection,
    existing_tracks: dict,
    match_iou: float = 0.25,
) -> Optional[str]:
    """Match a detection to an existing track by IoU overlap.

    Args:
        detection: A Detection instance.
        existing_tracks: Dict of track_id → track state.
        match_iou: Minimum IoU threshold (default 0.25, overridden
                   by runtime config).

    Returns:
        Matched track ID or None.
    """
    best_id = None
    best_iou = match_iou  # Minimum IoU threshold

    for tid, state in existing_tracks.items():
        iou = _bbox_iou(detection.bbox, state.get("bbox_last", []))
        if iou > best_iou:
            best_iou = iou
            best_id = tid

    return best_id


def _bbox_iou(bbox_a: list, bbox_b: list) -> float:
    """Compute IoU between two normalized bboxes [x1,y1,x2,y2]."""
    if len(bbox_a) != 4 or len(bbox_b) != 4:
        return 0.0
    x1 = max(bbox_a[0], bbox_b[0])
    y1 = max(bbox_a[1], bbox_b[1])
    x2 = min(bbox_a[2], bbox_b[2])
    y2 = min(bbox_a[3], bbox_b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
    area_b = (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _mint_track_id(camera_id: str, existing: dict) -> str:
    """Generate next sequential track ID for this camera."""
    prefix = camera_id[:6].upper().replace("-", "")
    existing_nums = []
    for tid in existing:
        try:
            existing_nums.append(int(tid.split("_")[-1]))
        except ValueError:
            pass
    next_num = max(existing_nums, default=0) + 1
    return f"{prefix}_{next_num:03d}"