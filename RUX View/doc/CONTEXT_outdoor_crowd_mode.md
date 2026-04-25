# CONTEXT.md — Outdoor / Crowd Mode
# Module: connect/camera/outdoor_mode.py + backend/ai/outdoor_decisions.py
# Sprint: 3.2
# Camera placement: Road-facing / front door / compound gate

---

## What This Module Does

Handles all detection logic for cameras pointed at public or semi-public outdoor
spaces — roads, front gates, compound entries, building facades.

Unlike Indoor mode (which tracks every person), Outdoor mode treats the scene
statistically. Individual tracking on a busy BD street = meaningless noise.
MOG2 learns the "normal" baseline over 24 hours, then fires only when something
deviates from that baseline significantly.

Two sub-contexts in this module:
1. CLIENT SIDE (outdoor_mode.py) — runs on customer Windows PC / Android
2. SERVER SIDE (outdoor_decisions.py) — runs on Cloud Run after trigger arrives

---

## Inputs

### Client side — outdoor_mode.py
```python
process_outdoor_frame(
    frame: np.ndarray,          # current BGR frame from RTSP
    prev_frame: np.ndarray,     # previous frame
    mog2_subtractor: cv2.BackgroundSubtractorMOG2,
    camera_config: dict         # mode, ignore_zones, sensitivity
) -> OutdoorMotionResult
```

### Server side — outdoor_decisions.py
```python
make_outdoor_decision(
    jpeg_bytes: bytes,          # best frame selected by frame_selector.py
    motion_result: dict,        # OutdoorMotionResult serialised from client
    camera_context: dict,       # camera name, location, mode config
    recent_events: list         # last 5 events for this camera (from DB)
) -> OutdoorDecision
```

---

## Outputs

### OutdoorMotionResult (client, returned to trigger_sender.py)
```python
@dataclass
class OutdoorMotionResult:
    should_trigger: bool         # send to server?
    trigger_reason: str          # "crowd_scatter" | "density_spike" |
                                 # "loitering" | "abandoned_object" |
                                 # "night_movement" | "fast_motion"
    pixel_change_pct: float      # 0.0 – 1.0, % of frame changed
    crowd_density_score: float   # 0.0 – 1.0 from MOG2 fg mask density
    motion_vector: str           # "approaching" | "passing" | "stationary"
    is_night: bool               # derived from frame brightness
    frame_brightness: float      # avg pixel brightness (0–255)
```

### OutdoorDecision (server, saved to events table)
```python
@dataclass
class OutdoorDecision:
    threat_level: str            # "LOW" | "MEDIUM" | "HIGH"
    incident_type: str           # "loitering" | "crowd_anomaly" |
                                 # "abandoned_object" | "suspicious_vehicle" |
                                 # "night_intrusion" | "normal_traffic"
    description: str             # Bangla-friendly summary for Telegram
    persons_description: list    # from Gemini analyse_frame()
    should_alert: bool
    alert_priority: str          # "immediate" | "digest_only" | "suppress"
    gate_crossing_count: int     # simple in/out tally (see D028)
    recommended_action: str      # text for Telegram alert body
```

---

## Dependencies

```
connect/camera/outdoor_mode.py
  → cv2.BackgroundSubtractorMOG2    (OpenCV, no install needed)
  → motion_detector.py              (imports contour_filter, aspect_ratio_filter)
  → frame_selector.py               (select_best_frame called after trigger)

backend/ai/outdoor_decisions.py
  → ai_client.py                    (analyse_frame, make_incident_decision)
  → database.py                     (fetch recent_events for context)
  → alert_router.py                 (called after decision if should_alert=True)
```

---

## Called By

```
connect/camera/
  → camera_loop.py calls process_outdoor_frame() every frame
  → trigger_sender.py reads OutdoorMotionResult.should_trigger

backend/api/
  → triggers.py receives JPEG + motion_result JSON from client
  → calls make_outdoor_decision() as background task
  → saves OutdoorDecision to events table
```

---

## Key Detection Logic

### MOG2 Setup (do once per camera stream)
```python
mog2 = cv2.createBackgroundSubtractorMOG2(
    history=500,        # ~17s at 30fps — learns baseline quickly
    varThreshold=50,    # higher = less sensitive (BD streets are noisy)
    detectShadows=False # shadows cause false positives outdoors
)
```

### Trigger Thresholds (Outdoor mode — higher than Indoor)
```
pixel_change_pct thresholds:
  < 0.03  → skip entirely (wind, leaves, camera shake)
  0.03–0.15 → check (single person passing — normal)
  0.15–0.40 → send to Gemini for analysis (unusual activity)
  > 0.40  → HIGH priority trigger (crowd scatter, running, fight)

Night multiplier: thresholds halved after frame_brightness < 40
  (any movement at night is more suspicious)
```

### Gate Line-Crossing Counter (D028 — simple implementation)
```python
# Virtual horizontal line at 60% of frame height (configurable)
# Track contour centroid crossing the line top→bottom (approach)
# vs bottom→top (leaving)
# Increment gate_crossing_count per trigger session
# Reset every hour, store hourly totals in analytics table
```

### motion_vector Detection
```python
# Compare centroid position of largest contour across 3 frames:
# centroid moving toward bottom-centre = "approaching"
# centroid moving horizontally         = "passing"
# centroid barely moving               = "stationary" (loitering candidate)
```

---

## Gemini Prompt Behaviour (outdoor context)

`analyse_frame()` is called with outdoor-specific context injected:

```
System hint passed to Gemini:
"This is an outdoor road-facing camera. Normal baseline includes
passing pedestrians and vehicles. Flag: groups of 3+ people
stopping together, anyone looking at the camera/building for
>10 seconds, vehicles parked directly in front of entry,
objects left unattended, running or physical altercations."
```

`make_incident_decision()` receives:
- The OutdoorMotionResult dict
- Gemini frame analysis
- Last 5 events (to detect repeat offender / escalation pattern)

---

## Camera Modes That Use This Module

| Mode | Uses outdoor_mode.py? | Notes |
|---|---|---|
| INDOOR | No | Uses indoor_mode.py |
| OUTDOOR | Yes — fully | Primary use case |
| PARKING | Partial | Uses vehicle-aware variant |
| MIXED | Yes — for outdoor zones | Zone mask applied first |
| SHOP | No | Uses shop_mode.py |

---

## Known Limitations

- MOG2 needs ~2 minutes of baseline before reliable detection
  → first 120 seconds after camera connect: suppress triggers, log as "calibrating"
- Heavy rain creates false positives (entire frame changes)
  → detect via: high pixel_change_pct + low contour count = rain heuristic → suppress
- Night IR cameras produce grain noise
  → apply Gaussian blur (5,5) before MOG2 on night frames
- Cannot distinguish car headlights from person at night reliably
  → Gemini tiebreaker always called for night HIGH triggers
- gate_crossing_count is approximate (contour centroid, not true tracking)
  → exact people counting deferred to V2 (ByteTrack)

---

## Test Fixtures Available

```
fixtures/test_frames/outdoor/
  → normal_street_day.jpg       single person passing — should NOT trigger HIGH
  → crowd_scatter.jpg           group suddenly dispersing — should trigger HIGH
  → loitering_gate.jpg          person stationary 45s — should trigger MEDIUM
  → parked_vehicle_front.jpg    car parked blocking gate — should trigger MEDIUM
  → night_movement.jpg          movement at 2am — should trigger HIGH
  → rain_false_positive.jpg     heavy rain — should be SUPPRESSED
  → abandoned_bag.jpg           bag left, person gone — should trigger HIGH

fixtures/test_audio/outdoor/
  → street_ambient.wav          normal traffic noise — should NOT trigger Whisper
  → shouting.wav                "chor chor" shout — should trigger Whisper
```

---

## Test Cases to Write (test_outdoor_mode.py)

```python
test_normal_pedestrian_does_not_trigger_high()
test_crowd_scatter_triggers_high()
test_loitering_detected_after_stationary_frames()
test_rain_heuristic_suppresses_trigger()
test_night_threshold_halved()
test_mog2_calibration_period_suppresses()
test_gate_crossing_count_increments_approach()
test_gate_crossing_count_increments_departure()
test_motion_vector_approaching_vs_passing()
test_gemini_context_injected_correctly()
test_outdoor_decision_saves_to_events_table()
test_high_threat_routes_to_alert_router()
```

---

## Key Decisions Applicable Here

- D005 — Trigger-only (not continuous stream) — MOG2 is the free local filter
- D008 — Camera modes separated — outdoor thresholds deliberately higher than indoor
- D017 — MOG2 chosen over ByteTrack for V1 outdoor — statistical, not per-person
- D026 — process_trigger() must be async — all Gemini calls use await
- D028 — Gate line-crossing counter — centroid-based, not ByteTrack

---

*CONTEXT.md — Outdoor/Crowd Mode*
*Sprint 3.2 | Vision OS V1*
