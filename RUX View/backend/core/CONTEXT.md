# CONTEXT.md — Core Module
# Module: backend/core/
# Sprint: 3.1 (incident_tracker), 3.4 (cross_camera, ghost, repeat_sighting), 3.6 (pipeline)
# Purpose: Incident state machine + multi-camera intelligence

---

## What This Module Does

Four files handling the core intelligence pipeline:

1. **pipeline.py** — Main orchestrator per camera (Sprint 3.6)
2. **incident_tracker.py** — IDLE/TRACKING/CLOSE state machine (Sprint 3.1)
3. **cross_camera.py** — Multi-camera correlation engine (Sprint 3.4)
4. **ghost_detector.py** — Unaccounted person detection (Sprint 3.4)
5. **repeat_sighting.py** — Frequency escalation logic (Sprint 3.4)

---

## File: incident_tracker.py

### State Machine
```
IDLE → (motion passes filters + cooldown elapsed) → TRACKING → (no motion 3-6s) → CLOSE
```

### CamState Enum
- IDLE: Gemma OFF, cost $0
- TRACKING: Gemma ON, burst every 2.5s when behaviour changes
- CLOSE: Send full timeline to Gemini, route alert, save to DB

### Functions
```python
class IncidentTracker:
    async def process(trigger: TriggerData) -> IncidentAction | None
    # Returns: GEMMA_CALL / BURST / CLOSE_INCIDENT / None
```

### Timing Parameters by Mode
```python
TIMING = {
    "indoor":  {"cooldown": 15, "burst": 2.5, "urgent": 0.8, "no_motion": 3, "max_cap": 60},
    "outdoor": {"cooldown": 30, "burst": 2.5, "urgent": 0.8, "no_motion": 6, "max_cap": 60},
    "parking": {"cooldown": 20, "burst": 2.5, "urgent": 0.8, "no_motion": 4, "max_cap": 120},
    "shop":    {"cooldown": 10, "burst": 2.5, "urgent": 0.8, "no_motion": 3, "max_cap": 300},
    "night":   {"cooldown": 8,  "burst": 1.5, "urgent": 0.8, "no_motion": 4, "max_cap": 60},
}
```

### Pixel Diff Thresholds
```python
THRESHOLDS = {
    "indoor":  {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "outdoor": {"skip": 800, "check": 4000, "gemma": 4000, "urgent": 10000},
    "parking": {"skip": 600, "check": 3500, "gemma": 3500, "urgent": 9000},
    "night":   {"skip": 300, "check": 2000, "gemma": 2000, "urgent": 5000},
}
```

### Loitering Escalation Timers
```python
LOITER = {
    "front_gate":       {"low": 45, "medium": 120, "high": 240},
    "parking_others":   {"low": 45, "medium": 90, "high": 150},
    "parking_afterhrs": {"low": 15, "medium": 30, "high": 60},
    "indoor_general":   {"low": 60, "medium": 180, "high": 300},
}
```

---

## File: cross_camera.py

### Functions
```python
async def correlate_across_cameras(person_id: str, source_camera_id: str, location_id: str, event_timestamp: datetime, direction: str) -> CrossCameraResult
async def check_ghost_condition(person_id: str, location_id: str, entry_camera_id: str, entry_timestamp: datetime) -> GhostCheckResult
```

### Key Rules
- NEVER crosses location boundary (HARD RULE enforced in SQL)
- Camera topology from user config
- Unexpected gap detection (person at cam_3 without passing cam_2)

---

## File: ghost_detector.py

### Logic
- Person enters → schedule check at 10min + 30min
- 10min: MEDIUM alert "Person entered, not seen leaving"
- 30min: HIGH alert "Unaccounted person on property"
- Cancelled if: person seen on any camera OR user dismisses

---

## File: repeat_sighting.py

### Escalation
- 1st: LOG only
- 2nd: LOW alert
- 3rd: MEDIUM + "seen X times today"
- 4th: HIGH + emergency voice note
- 5th+: HIGH every time

### Reset
- 6 hours no sighting → reset
- Night hours (10pm-6am) NEVER reset
- After hours at business NEVER reset

---

## File: pipeline.py

### Orchestration Flow
```
process_trigger(jpeg, audio, meta)
  → incident_tracker.process()
  → if GEMMA_CALL: ai_client.analyse_frame()
  → if person: reid_engine.get_or_create_person()
  → cross_camera.correlate_across_cameras()
  → repeat_sighting.record_sighting()
  → ghost_detector.track_entry()
  → ai_client.make_incident_decision()
  → alert_router.route_alert()
  → database.save_event()
```

### Key Decisions
- **D005** — Trigger-only architecture (not continuous streaming)
- **D026** — All calls async, use asyncio.gather() for parallel AI calls

## Dependencies
- backend/ai/ai_client.py
- backend/ai/reid_engine.py
- backend/modes/*.py
- backend/alerts/alert_router.py
- backend/storage/database.py

## Called By
- backend/api/triggers.py
