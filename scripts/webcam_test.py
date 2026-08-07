"""
webcam_test.py — Vision OS webcam integration test.

Reads from laptop webcam (device index 0), sends frames
to the backend trigger endpoint, and measures:
  - End-to-end latency (frame captured → response received)
  - Duplicate detection (same event ID returned twice?)
  - Dashboard update speed (check manually after running)

Usage:
    python scripts/webcam_test.py

Requirements:
    pip install opencv-python httpx

Config (edit these):
"""

import asyncio
import base64
import time
import json
from datetime import datetime, timezone
from collections import defaultdict

import cv2
import httpx

# ── Config ────────────────────────────────────────────────────
BACKEND_URL   = "https://visionos-backend-1004956364101.us-central1.run.app"
API_TOKEN     = "dev-token"
CAMERA_ID     = "webcam-test-001"
CAMERA_NAME   = "Laptop Webcam Test"
MODE          = "indoor"
WEBCAM_INDEX  = 0       # 0 = default laptop camera
SEND_INTERVAL = 3.0     # seconds between triggers
TOTAL_TRIGGERS = 10     # how many frames to send
JPEG_QUALITY  = 85

# ── Results tracking ──────────────────────────────────────────
results = []
event_ids = []
latencies = []

def capture_frame(cap) -> bytes | None:
    """Capture one frame from webcam and encode as JPEG bytes."""
    ret, frame = cap.read()
    if not ret or frame is None:
        return None
    _, buf = cv2.imencode(
        ".jpg", frame,
        [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    )
    return buf.tobytes()

async def send_trigger(client: httpx.AsyncClient, jpeg_bytes: bytes, i: int) -> dict:
    """Send one frame trigger to backend and return result."""
    image_b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    payload = {
        "camera_id":   CAMERA_ID,
        "image_base64": image_b64,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "mode":        MODE,
        "confidence":  1.0,
    }

    t0 = time.monotonic()
    try:
        resp = await client.post(
            f"{BACKEND_URL}/api/triggers/frame",
            json=payload,
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=60.0,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Check for empty response first
        if not resp.content:
            print(f"  [{i:02d}] {latency_ms:4d}ms  EMPTY RESPONSE — status={resp.status_code}")
            return {
                "trigger": i,
                "latency_ms": latency_ms,
                "status": "empty_response",
                "event_id": None,
                "http_status": resp.status_code,
            }

        # Check for non-200 status before JSON parsing
        if resp.status_code != 200:
            body = resp.text[:300]
            print(f"  [{i:02d}] {latency_ms:4d}ms  HTTP {resp.status_code}: {body}")
            return {
                "trigger": i,
                "latency_ms": latency_ms,
                "status": "http_error",
                "event_id": None,
                "http_status": resp.status_code,
                "error": body,
            }

        data = resp.json()

        status = data.get("status", "unknown")
        event_id = data.get("event_id")
        threat = data.get("threat_level", "—")

        print(
            f"  [{i:02d}] {latency_ms:4d}ms  "
            f"status={status:<12}  "
            f"threat={threat:<10}  "
            f"event_id={str(event_id)[:12] if event_id else 'none'}"
        )

        return {
            "trigger": i,
            "latency_ms": latency_ms,
            "status": status,
            "event_id": event_id,
            "threat_level": threat,
            "http_status": resp.status_code,
        }

    except Exception as e:
        latency_ms = int((time.monotonic() - t0) * 1000)
        print(f"  [{i:02d}] {latency_ms:4d}ms  ERROR: {e}")
        return {
            "trigger": i,
            "latency_ms": latency_ms,
            "status": "error",
            "event_id": None,
            "error": str(e),
        }

def analyse_results(results: list[dict]) -> None:
    """Print test summary and flag issues."""
    print("\n" + "═" * 60)
    print("TEST SUMMARY")
    print("═" * 60)

    total = len(results)
    errors = [r for r in results if r.get("status") == "error"]
    no_changes = [r for r in results if r.get("status") == "no_change"]
    events_created = [r for r in results if r.get("event_id")]
    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]

    print(f"Total triggers sent : {total}")
    print(f"Errors              : {len(errors)}")
    print(f"No-change (YOLO gate): {len(no_changes)}")
    print(f"Events created      : {len(events_created)}")

    if latencies:
        print(f"Latency — min       : {min(latencies)}ms")
        print(f"Latency — max       : {max(latencies)}ms")
        print(f"Latency — avg       : {int(sum(latencies)/len(latencies))}ms")

    # Duplicate check
    event_id_list = [r["event_id"] for r in results if r.get("event_id")]
    seen = defaultdict(int)
    for eid in event_id_list:
        seen[eid] += 1
    dupes = {eid: count for eid, count in seen.items() if count > 1}

    if dupes:
        print(f"\n⚠️  DUPLICATE EVENT IDs DETECTED: {len(dupes)}")
        for eid, count in dupes.items():
            print(f"   {eid}: returned {count} times")
    else:
        print(f"\n✅ No duplicate event IDs")

    # Threat distribution
    threat_counts = defaultdict(int)
    for r in results:
        threat_counts[r.get("threat_level", "—")] += 1
    print("\nThreat distribution:")
    for threat, count in sorted(threat_counts.items()):
        print(f"   {threat:<12}: {count}")

    # Flag if avg latency > 5s
    if latencies and sum(latencies)/len(latencies) > 5000:
        print("\n⚠️  HIGH LATENCY: Average >5s. Check Cloud Run cold start.")
    elif latencies and sum(latencies)/len(latencies) < 2000:
        print("\n✅ LATENCY OK: Average <2s")

    print("\nNow check your dashboard:")
    print(f"  https://visionos-1004956364101.us-central1.run.app/dashboard/events")
    print(f"  Camera filter: {CAMERA_NAME}")
    print(f"  Expected: {len(events_created)} events, no duplicates\n")

async def main():
    print("Vision OS — Webcam Integration Test")
    print("=" * 60)
    print(f"Backend : {BACKEND_URL}")
    print(f"Camera  : {CAMERA_ID}")
    print(f"Triggers: {TOTAL_TRIGGERS} frames, {SEND_INTERVAL}s apart")
    print("=" * 60)

    # Open webcam
    print(f"\nOpening webcam (index {WEBCAM_INDEX})...")
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam. Check WEBCAM_INDEX.")
        return

    # Warm up (first frame is often blank)
    for _ in range(3):
        cap.read()
    print("Webcam ready.\n")

    print("Sending triggers — move in front of camera to trigger events:")
    print("-" * 60)

    async with httpx.AsyncClient() as client:
        for i in range(1, TOTAL_TRIGGERS + 1):
            jpeg = capture_frame(cap)
            if jpeg is None:
                print(f"  [{i:02d}] Frame capture failed — skipping")
                continue

            result = await send_trigger(client, jpeg, i)
            results.append(result)

            if i < TOTAL_TRIGGERS:
                await asyncio.sleep(SEND_INTERVAL)

    cap.release()
    analyse_results(results)

    # Save raw results
    with open("scripts/webcam_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Raw results saved to scripts/webcam_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())