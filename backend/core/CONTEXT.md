# CONTEXT.md — Core Module
# Module: backend/core/
# Purpose: Core AI pipeline orchestrators + detection stack

---

## What This Module Does

Eight files and a subdirectory handling the core intelligence pipeline:

### Pipeline Orchestrators
1. **pipeline.py** — `CameraPipeline` class, per-camera orchestrator (V1 fallback)
2. **pipeline_v2.py** — `PipelineV2` class, upgraded pipeline with YOLO gate + BoT-SORT (production)
3. **pipeline_manager.py** — `PipelineManager` factory, manages per-camera pipeline instances
4. **incident_tracker.py** — `IncidentTracker`, IDLE/TRACKING/CLOSE state machine

### Multi-Camera Intelligence
5. **cross_camera.py** — `CrossCameraCorrelator`, multi-camera correlation engine
6. **ghost_detector.py** — `GhostDetector`, unaccounted person detection
7. **repeat_sighting.py** — `RepeatSightingTracker`, frequency escalation logic

### Detection Subdirectory (backend/core/detection/)
8. **detection/yolo_detector.py** — YOLOv8 nano ONNX detection gate
9. **detection/botsort_tracker.py** — BoT-SORT multi-object tracker with Redis state
10. **detection/incident_builder.py** — Gemini call gating logic based on track state

---

## Pipeline V2 Flow (Production — Default)

```
JPEG frame
  → Stage 1: YOLO gate (detection/yolo_detector.py)
      Filters frames with no relevant objects (person/vehicle/animal).
      Confidence threshold: 0.35, NMS IoU: 0.45.
      Relevant classes: person, bicycle, car, motorcycle, bus, truck, cat, dog.
      Returns DetectionResult with bboxes, annotated JPEG, object_summary.
      ~200ms inference on CPU (i5-8350U).

  → Stage 2: BoT-SORT tracker (detection/botsort_tracker.py)
      Assigns persistent Track IDs per camera using IoU matching (min 0.25).
      State stored in Upstash Redis: key="track:{camera_id}", TTL=300s.
      Returns TrackingResult with tracks, new_tracks, lost_tracks, track_summary.

  → Stage 3: Incident builder (detection/incident_builder.py)
      Decides if Gemini call is warranted:
      - New track appeared → CALL
      - No Gemini call in 120s → CALL (periodic update)
      - Track count changed ±2 → CALL
      - Otherwise → SKIP (return PipelineResult with change_detected=False)

  → Stage 4: CameraPipeline.process_trigger() (V1 fallback)
      If YOLO unavailable → passes through directly.
      Runs: frame quality gate → Gemini vision → Re-ID → cross-camera → alerts
```

### Pipeline V2 Class (pipeline_v2.py)

```python
class PipelineV2:
    def __init__(self, pipeline_manager, redis_client):
        # pipeline_manager: Existing PipelineManager instance
        # redis_client: Upstash async Redis client

    async def process_frame(
        camera_id: str,
        user_id: str,
        location_id: str,
        mode: str,
        jpeg_bytes: bytes,
        camera_profile: dict | None = None,
    ) -> PipelineResult:
        """Process a single frame through YOLO gate → tracker → incident builder
        → existing CameraPipeline."""
```

---

## Pipeline V1 Flow (Fallback)

```
Trigger → IncidentTracker.process()
  → If GEMMA_CALL: Gemini vision analysis (analyse_frame_structured)
  → If persons found: Re-ID engine → cross-camera correlation
  → If CLOSE_INCIDENT: Gemini incident decision → alert routing → DB save
```

### File: pipeline_manager.py

```python
class PipelineManager:
    """Manages CameraPipeline instances across all cameras.
    Creates one CameraPipeline per camera on first trigger.
    """
    def __init__(self): ...
    async def initialize(self) -> None: ...
    async def process_trigger(camera_id, user_id, location_id, mode,
                               jpeg_bytes, audio_bytes, motion_result,
                               yamnet_result, camera_profile) -> PipelineResult: ...
    async def shutdown(self) -> None: ...
```

### File: pipeline.py (CameraPipeline)

```python
class CameraPipeline:
    """Main pipeline orchestrator for a single camera."""
    def __init__(self, camera_id, user_id, location_id, mode, db_session_factory): ...
    async def process_trigger(ctx: PipelineContext) -> PipelineResult: ...
```

---

## Incident State Machine (incident_tracker.py)

```
IDLE → (motion passes filters + cooldown elapsed) → TRACKING
TRACKING → (no motion 3-6s, mode dependent) → CLOSE
CLOSE → incident decision + alert + DB → back to IDLE
```

### CamState Enum
- IDLE: Gemini OFF, cost $0
- TRACKING: Gemini ON, burst when behaviour changes
- CLOSE: Send timeline to Gemini, route alert, save to DB

---

## Cross-Camera Intelligence

### CrossCameraCorrelator (cross_camera.py)
```python
async def correlate_across_cameras(person_id, source_camera_id,
                                    location_id, event_timestamp) -> CrossCameraResult
```
- NEVER crosses location boundary (HARD RULE enforced in SQL)
- Camera topology from user config
- Unexpected gap detection

### GhostDetector (ghost_detector.py)
- Person enters → schedule check at 10min + 30min
- 10min: MEDIUM alert "Person entered, not seen leaving"
- 30min: HIGH alert "Unaccounted person on property"
- Cancelled if person seen on any camera or user dismisses

### RepeatSightingTracker (repeat_sighting.py)
- 1st: LOG only | 2nd: LOW | 3rd: MEDIUM | 4th: HIGH + emergency | 5th+: HIGH
- Reset: 6h no sighting | Night hours NEVER reset | After hours NEVER reset

---

## Key Design Decisions

| Decision | Detail |
|----------|--------|
| D005 | Trigger-only architecture (not continuous streaming) |
| D026 | All calls async, use asyncio.gather() for parallel AI calls |
| YOLO gate | Reduces Gemini calls by ~40% via ONNX Runtime |
| NO_CHANGE | Short-circuit reduces additional ~30% |
| Redis state | Track state in Upstash Redis (not in-memory) for Cloud Run stateless containers |
| IoU matching | Bbox overlap for track continuity (min IoU 0.25) |
| Gemini throttle | Max 1 call per 120s per camera (incident builder) + 1 per 8s global |

---

## Dependencies
- Upstash Redis (required for BoT-SORT tracker state)
- ONNX Runtime (required for YOLO gate)
- Vertex AI / google-cloud-aiplatform (Gemini)
- pgvector (Re-ID similarity search)
- opencv-python (frame quality checks, MOG2)

## Called By
- backend/api/triggers.py (via PipelineManager.process_trigger or PipelineV2.process_frame)
- backend/dashboard/server.py (initializes PipelineManager in lifespan)