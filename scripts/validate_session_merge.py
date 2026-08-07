"""
validate_session_merge.py — Offline validation of the session-merge fix
against a real video clip, without needing a live server, Redis, GCP
credentials, or a database.

Runs the real backend YOLO gate (backend/core/detection/yolo_detector.py,
same ONNX model connect/ uses on-device) frame-by-frame against a clip, then
replays that exact real per-frame detection sequence through both the OLD
(pre-fix) and NEW (current) backend/api/triggers.py session-merge state
machines. Reports how many events each would have created for one
continuous visit — this is the direct, credible way to check "does one
person's walk through frame still turn into 10-15 events" without wiring up
Vertex AI / Upstash / Postgres.

Usage:
    python -m scripts.validate_session_merge --clip path/to/clip.mp4
    python -m scripts.validate_session_merge --clip clip.mp4 --fps 10 --confidence 0.35

Notes:
    - Only exercises the YOLO-gate layer of the session-merge decision
      (the actual bug: a transient no-object frame during an active
      session used to tear the session down). It does not exercise the
      BoT-SORT tracker or incident builder throttle, which need Redis.
    - Sampling at --fps is denser than a real client's cadence (connect/'s
      MOTION_COOLDOWN is 30s between triggers), so this is a stress test
      in the fix's favor, not a 1:1 reproduction of real trigger timing —
      both OLD and NEW logic see the identical sequence, so the
      before/after comparison is still fair.
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from backend.core.detection.yolo_detector import detect

SESSION_TIMEOUT_SEC = 180


def extract_and_detect(clip_path: str, target_fps: int, confidence: float):
    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open clip: {clip_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_skip = max(1, round(src_fps / target_fps))
    config = {"yolo_confidence_threshold": confidence, "nms_iou_threshold": 0.45}

    sequence = []
    frame_number = 0
    extracted = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_number += 1
            if frame_number % frame_skip != 0:
                continue
            ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            ok, jpeg_buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                continue
            result = detect(jpeg_buf.tobytes(), annotate=False, config=config)
            sequence.append((extracted, ts, result.has_relevant_objects, result.object_summary))
            extracted += 1
    finally:
        cap.release()

    return sequence, src_fps, frame_skip


def _simulate(sequence, old_bug: bool) -> int:
    """Replay a (idx, timestamp_sec, has_relevant_objects, summary) sequence
    through the session-merge state machine.

    old_bug=True reconstructs the pre-fix behavior (git commit eb900fb's
    parent): a yolo_gate no-change result during an active session pops
    the session. old_bug=False is the current, fixed behavior: any
    no-change result during an active session just extends last_motion_at.

    Session *creation* (first frame of a would-be new session) is
    identical in both: a yolo_gate miss on frame 1 never opens a session
    at all — that half of the logic was never the bug.
    """
    active = None
    events = 0
    base = datetime.now(timezone.utc)

    for _, ts, hit, _ in sequence:
        now = base + timedelta(seconds=ts)
        if active is not None and (now - active["last_motion_at"]).total_seconds() >= SESSION_TIMEOUT_SEC:
            active = None
        if active is not None:
            if not hit and old_bug:
                active = None
                continue
            active["last_motion_at"] = now
        else:
            if not hit:
                continue
            events += 1
            active = {"last_motion_at": now}
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", required=True, help="Path to an mp4 clip")
    parser.add_argument("--fps", type=int, default=10, help="Frame extraction rate (default: 10, matches clip_analysis.py)")
    parser.add_argument("--confidence", type=float, default=0.35, help="yolo_confidence_threshold override (default: 0.35)")
    args = parser.parse_args()

    sequence, src_fps, frame_skip = extract_and_detect(args.clip, args.fps, args.confidence)
    if not sequence:
        print("No frames extracted — check the clip path/codec.")
        return

    hits = sum(1 for _, _, hit, _ in sequence if hit)
    pattern = "".join("1" if hit else "0" for _, _, hit, _ in sequence)
    flickers = sum(
        1 for i in range(1, len(sequence) - 1)
        if sequence[i - 1][2] and not sequence[i][2] and sequence[i + 1][2]
    )
    summaries = [s for _, _, hit, s in sequence if hit and s]

    old_events = _simulate(sequence, old_bug=True)
    new_events = _simulate(sequence, old_bug=False)

    print(f"=== {Path(args.clip).name} ===")
    print(f"Source fps={src_fps:.1f}, extracted {len(sequence)} frames @ ~{args.fps}fps (frame_skip={frame_skip}, confidence={args.confidence})")
    print(f"YOLO gate: {hits}/{len(sequence)} frames had a relevant object ({hits / len(sequence) * 100:.1f}%)")
    print(f"Pattern (1=detected, 0=yolo_gate miss): {pattern}")
    print(f"Isolated single-frame flicker gaps: {flickers}")
    if summaries:
        print(f"Sample object summary: {summaries[0]}")
    print()
    print("=== Session-merge comparison (identical real per-frame sequence) ===")
    print(f"OLD (pre-fix) logic would create: {old_events} event(s)")
    print(f"NEW (current) logic creates:      {new_events} event(s)")


if __name__ == "__main__":
    main()
