# CONTEXT.md — Camera Modes Module
# Module: backend/modes/
# Sprint: 3.2
# Purpose: Per-mode detection parameters and logic

---

## What This Module Does

Five files, one per camera mode. Each provides mode-specific parameters
and detection logic used by the incident tracker and pipeline.

---

## Files

### indoor_mode.py
- Full individual tracking
- Re-ID enabled
- Loitering detection
- Ghost detection
- Whisper enabled
- Familiar faces
- Night mode automatic

### outdoor_mode.py
- MOG2 background subtraction (statistical, not per-person)
- Crowd anomaly detection
- No individual tracking (public space)
- Higher thresholds (BD streets are noisy)
- Gate line-crossing counter (D028)

### parking_mode.py
- Vehicle + person-vehicle interaction detection
- Day/night parameter switching
- Headlight detection at night
- Cross-camera with gate camera

### mixed_mode.py
- Zone-based split (property zone + public zone)
- Person crossing public→property triggers full tracking
- Public zone: outdoor logic only

### shop_mode.py
- Customer counting + demographics
- Staff filter (Re-ID based)
- Business hours switching
- After-hours → security mode
- Godown specifics (strict after hours)

---

## Functions (each file)

```python
def get_motion_params(mode: str) -> MotionParams
    # Returns: {skip_threshold, check_threshold, gemma_threshold, urgent_threshold}

def get_timing_params(mode: str, is_night: bool = False) -> TimingParams
    # Returns: {cooldown, burst_interval, urgent_interval, no_motion_timeout, max_cap_duration}

def get_loiter_params(mode: str, location_type: str) -> LoiterParams
    # Returns: {low_seconds, medium_seconds, high_seconds}

def should_analyse_individual(mode: str, zone: str = None) -> bool
    # Returns: True for indoor/parking, False for outdoor public zone
```

## Key Decisions
- **D008** — Five separate modes (not one-size-fits-all)
- **D017** — MOG2 for outdoor (statistical, not per-person)
- **D028** — Gate line-crossing counter (centroid-based)

## Dependencies
- None (pure data + logic)

## Called By
- backend/core/incident_tracker.py
- backend/core/pipeline.py
