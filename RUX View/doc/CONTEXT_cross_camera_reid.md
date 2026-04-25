# CONTEXT.md — Cross-Camera Correlation + Re-ID Engine
# Module: backend/ai/reid_engine.py + backend/ai/cross_camera.py
# Sprint: 3.3
# Use case: Residential area multi-camera person tracking

---

## What This Module Does

Two tightly coupled responsibilities handled in two files:

**reid_engine.py** — Given a person crop (JPEG bbox cutout), generate a
512-dim embedding vector using BoxMOT's FastReID backend. Compare against
known persons in pgvector. Return: matched person_id or create new person record.

**cross_camera.py** — Given a confirmed person sighting at Camera A, query
other cameras at the SAME location to find recent sightings of the same person.
Build a movement timeline. Trigger ghost detection if person entered but
never appeared at expected exit camera.

This is the core of the residential area intelligence — knowing that the
person who passed the front gate (cam_1) is now at the back garden (cam_3)
is what makes Vision OS genuinely useful vs a dumb DVR.

---

## Inputs

### reid_engine.py
```python
get_or_create_person(
    jpeg_crop: bytes,            # tight crop around detected person bbox
    camera_id: str,
    location_id: str,
    appearance_str: str,         # from Gemini: "blue shirt, black trousers, male"
    timestamp: datetime
) -> PersonMatch

embed_person_crop(
    jpeg_crop: bytes             # tight crop, min 64x128px recommended
) -> np.ndarray                  # shape: (512,) float32 embedding vector
```

### cross_camera.py
```python
correlate_across_cameras(
    person_id: str,              # confirmed from reid_engine
    source_camera_id: str,       # camera where person was just seen
    location_id: str,            # NEVER crosses location boundary
    event_timestamp: datetime,
    direction: str               # "entering" | "exiting" | "unknown"
) -> CrossCameraResult

check_ghost_condition(
    person_id: str,
    location_id: str,
    entry_camera_id: str,
    entry_timestamp: datetime
) -> GhostCheckResult
```

---

## Outputs

### PersonMatch (from reid_engine.py)
```python
@dataclass
class PersonMatch:
    person_id: str               # UUID — existing or newly created
    is_new_person: bool
    match_confidence: float      # cosine similarity score (0.0–1.0)
    match_method: str            # "embedding" | "string_match" | "gemini_tiebreaker"
    familiar_label: str | None   # "Dad", "Regular Visitor", None
    visit_count: int             # how many times seen at this location
    last_seen: datetime | None
    alert_on_sight: bool         # user-flagged watchlist person
```

### CrossCameraResult (from cross_camera.py)
```python
@dataclass
class CrossCameraResult:
    person_id: str
    movement_path: list[dict]    # [{camera_id, camera_name, timestamp, direction}]
    time_between_cameras: int    # seconds
    is_expected_path: bool       # matches known camera topology
    unexpected_gap: bool         # appeared at cam_3 without passing cam_2
    trigger_ghost_check: bool    # should ghost detector run?
```

### GhostCheckResult (from cross_camera.py)
```python
@dataclass
class GhostCheckResult:
    person_id: str
    minutes_since_entry: int
    expected_exit_camera: str | None
    seen_at_exit: bool
    ghost_alert_level: str       # "none" | "warn_10min" | "high_30min"
    alert_message: str           # Telegram-ready text
```

---

## Dependencies

```
backend/ai/reid_engine.py
  → boxmot                     pip install boxmot (FastReID backend)
  → database.py                persons table, pgvector similarity query
  → ai_client.py               reid_tiebreaker() for 0.50–0.72 cosine range

backend/ai/cross_camera.py
  → database.py                events table, cameras table, scene_states
  → reid_engine.py             PersonMatch is input to correlation
  → alert_router.py            ghost alert goes here if confirmed
```

---

## Called By

```
backend/api/triggers.py
  → After outdoor_decisions.py or indoor_decisions.py completes:
  → If person detected: call get_or_create_person()
  → Then call correlate_across_cameras()
  → If trigger_ghost_check: schedule check_ghost_condition() via APScheduler
     (10 min delay + 30 min delay — not immediate)
```

---

## Re-ID Matching Logic (3-tier cascade)

### Tier 1 — Embedding Similarity (primary)
```python
# pgvector query:
SELECT person_id, appearance_str, familiar_label,
       1 - (embedding <=> query_embedding) AS cosine_sim
FROM persons
WHERE location_id = :location_id          # HARD FILTER — never cross locations
  AND last_seen > NOW() - INTERVAL '2h'  # only recent sightings matter
ORDER BY embedding <=> query_embedding
LIMIT 5;

# Decision:
cosine_sim >= 0.73  → MATCH (same person, high confidence)
cosine_sim 0.50–0.72 → UNCERTAIN (go to Tier 2)
cosine_sim < 0.50   → NO MATCH (new person)
```

### Tier 2 — Appearance String Match (tiebreaker for uncertain range)
```python
# Compare Gemini appearance strings:
# "blue shirt, black trousers, male, ~30s"  vs stored appearance
# Jaccard similarity on tokenised description
# If similarity > 0.6 AND cosine in uncertain range → lean toward MATCH

jaccard_sim = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
```

### Tier 3 — Gemini Tiebreaker (only if still uncertain after Tier 2)
```python
# ai_client.reid_tiebreaker(emb1_desc, emb2_desc) → {match: bool, confidence: str}
# Called max once per trigger — API cost gate
# Result cached: if tiebreaker said "no match", don't re-ask for 30min
```

### Accuracy Targets (from D007)
```
Tier 1 only:       ~88–92% on clear crops
Tier 1 + 2:        ~91–94%
Tier 1 + 2 + 3:    ~93–95%
Graceful fallback: if all fail → new person (false negative better than false positive)
```

---

## Cross-Camera Topology

User defines camera relationships during setup (dashboard settings page).
Stored in `camera_topology` table.

```
Example residential layout:
  cam_1 (Front Gate) → can_reach → cam_2 (Front Door), cam_5 (Side Path)
  cam_2 (Front Door) → can_reach → cam_3 (Living Room), cam_4 (Stairwell)
  cam_3 (Living Room) → can_reach → cam_4 (Stairwell)
  cam_5 (Side Path) → can_reach → cam_4 (Stairwell), cam_6 (Back Garden)

Expected travel times (user configures, defaults provided):
  cam_1 → cam_2: 30–90 seconds
  cam_2 → cam_3: 10–30 seconds
  cam_1 → cam_5: 20–60 seconds
```

```python
# Unexpected gap detection:
# Person seen at cam_1 at T=0
# Person seen at cam_3 at T=120s
# cam_1 → cam_3 requires passing cam_2
# cam_2 has NO sighting in T=0 to T=120
# → unexpected_gap = True → escalate to MEDIUM alert
# "Person reached living room without being seen at front door"
```

---

## Ghost Detection Logic (D016)

```
Entry event: person seen at cam_1 (Front Gate) entering
Expected: person should appear at cam_2 within 90s
          OR person should re-appear at cam_1 exiting

APScheduler job scheduled at entry_time + 10 minutes:
  → check_ghost_condition(person_id, location_id, ...)
  → If not seen at any camera in 10 min: ghost_alert_level = "warn_10min"
  → Telegram: "⚠️ Person entered front gate 10 minutes ago.
               Not seen inside or leaving. [thumbnail]"

APScheduler job scheduled at entry_time + 30 minutes:
  → If still not seen: ghost_alert_level = "high_30min"
  → Telegram HIGH alert + SMS fallback (if HIGH policy)
  → "🚨 UNACCOUNTED PERSON — entered 30 min ago, not seen since."

Dismissal: user taps "Dismiss" in Telegram inline button → cancels pending job
False positive mitigation:
  → If person exits via cam_1 within window → cancel both jobs
  → If any camera sees matching person → cancel both jobs
```

---

## Location Boundary — HARD RULE

```python
# This check must exist at the TOP of every DB query in this module:
assert source_camera_id in get_cameras_for_location(location_id)
# Person from location_id="home_mirpur" NEVER matched against
# persons from location_id="shop_gulshan"
# Same person cannot be in two locations simultaneously
# This is enforced at query level (WHERE location_id = :location_id)
# NOT just application logic — the SQL filter is the guarantee
```

---

## pgvector Schema Reference

```sql
-- persons table (relevant columns)
CREATE TABLE persons (
    person_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id   VARCHAR NOT NULL,
    embedding     vector(512),          -- FastReID output
    appearance_str TEXT,                -- Gemini description string
    familiar_label VARCHAR,             -- user-assigned name
    visit_count   INTEGER DEFAULT 1,
    first_seen    TIMESTAMP,
    last_seen     TIMESTAMP,
    alert_on_sight BOOLEAN DEFAULT FALSE
);

CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- camera_topology table
CREATE TABLE camera_topology (
    from_camera_id VARCHAR,
    to_camera_id   VARCHAR,
    expected_min_seconds INTEGER,
    expected_max_seconds INTEGER,
    location_id    VARCHAR NOT NULL
);
```

---

## Known Limitations

- FastReID crop quality degrades heavily below 64×128px
  → If bbox crop is smaller: skip embedding, use string_match only, log warning
- Re-ID fails on identical clothing (twins, uniforms)
  → Accepted limitation for V1; Gemini tiebreaker helps somewhat
- Ghost detection has no ground truth for "expected exit camera"
  → If topology not configured by user, ghost check is disabled for that location
- pgvector IVFFlat index needs ~100 vectors before ANN is faster than exact scan
  → Below 100 persons per location: exact scan is fine, no action needed
- Cross-camera time window hardcoded at 2 hours
  → Person not seen for >2h treated as "left" — ghost jobs cancelled

---

## Test Fixtures Available

```
fixtures/person_crops/
  → same_person_angle_a.jpg     same person, different angle — should MATCH
  → same_person_angle_b.jpg     same person, different angle — should MATCH
  → different_person.jpg        different person, similar clothing — should NOT MATCH
  → low_quality_crop.jpg        48×96px — should fall back to string_match
  → uniform_person_a.jpg        security guard A
  → uniform_person_b.jpg        security guard B (same uniform) — UNCERTAIN expected

fixtures/topology/
  → test_location_topology.json  5-camera residential layout for tests
```

---

## Test Cases to Write

```python
# reid_engine.py tests
test_embed_returns_512_dim_vector()
test_high_cosine_sim_returns_match()
test_low_cosine_sim_creates_new_person()
test_uncertain_range_triggers_string_match()
test_string_match_tiebreaker_resolves_uncertain()
test_gemini_tiebreaker_called_only_in_uncertain_range()
test_location_boundary_never_crossed()
test_small_crop_skips_embedding_uses_string()
test_visit_count_increments_on_match()
test_alert_on_sight_person_triggers_high()

# cross_camera.py tests
test_expected_path_detected()
test_unexpected_gap_detected()
test_ghost_check_scheduled_on_entry()
test_ghost_cancelled_on_exit_sighting()
test_ghost_warn_at_10min()
test_ghost_high_at_30min()
test_location_boundary_enforced_in_sql()
test_topology_missing_disables_ghost()
```

---

## Key Decisions Applicable Here

- D007 — BoxMOT (FastReID) replaces torchreid — pip install boxmot
- D016 — Ghost detection logic — 10min warn, 30min HIGH, user dismissal
- D022 — pgvector for embedding storage and cosine similarity search
- D026 — All DB + Gemini calls must be async (await)

---

*CONTEXT.md — Cross-Camera Correlation + Re-ID Engine*
*Sprint 3.3 | Vision OS V1*
