# CONTEXT.md — AI Module
# Module: backend/ai/
# Purpose: All AI/ML operations

---

## What This Module Does

Three files handling all AI operations:

1. **ai_client.py** — Vertex AI Gemini 2.x Flash unified client (vision + reasoning + audio + queries + digests)
2. **reid_engine.py** — Person Re-ID with pgvector cosine similarity
3. **query_engine.py** — Natural language query processing

---

## File: ai_client.py

Unified client for ALL Gemini operations via Vertex AI SDK (`google-cloud-aiplatform`).
Model: `gemini-2.5-flash` (may be updated to newer 2.x versions).
Authentication: Application Default Credentials (ADC) — no API key needed.

### Imports
```python
import vertexai
from vertexai.generative_models import GenerativeModel, Part
```

### Functions (7 prompt types)

| Function | Prompt | Purpose | Structured Result |
|----------|--------|---------|-------------------|
| `analyse_frame()` | LIVE_VISION_PROMPT | Fast vision analysis for incidents | persons, scene_alerts, vehicles, change_detected |
| `analyse_frame_structured()` | STRUCTURED_ANALYSIS_PROMPT | Controlled-vocabulary JSON | event_type, threat_level, confidence, description, change_detected. Validates schema. Retries once on failure. Discards if confidence < 0.6. |
| `analyse_frame_with_second_pass()` | SECOND_PASS_PROMPT | Two-layer: vision → text → verdict | persons + threat_level, alert_message, action |
| `analyse_frame_detailed()` | QUERY_PROMPT | Exhaustive for NL queries | Detailed persons (clothing, accessories, position), scene, anomalies |
| `analyse_shop_entry()` | SHOP_ENTRY_PROMPT | Shop demographics | gender, age_group, carried_items, group_size, confidence |
| `analyse_audio()` | AUDIO_ANALYSIS_PROMPT | Audio transcription + threat detection | transcript, language, threat_detected, threat_level, threat_types, confidence |
| `make_incident_decision()` | INCIDENT_DECISION_PROMPT | Security verdict from timeline | threat_level, alert_message, action, reasoning, person_ids |
| `answer_query()` | QUERY_ANSWER_PROMPT | NL question answering | Plain text answer |
| `answer_scene_state()` | SCENE_STATE_PROMPT | Gate/door status queries | Plain text answer |
| `generate_daily_digest()` | DAILY_DIGEST_PROMPT | Daily summary | Text (200 word cap for free tier) |
| `generate_weekly_digest()` | WEEKLY_DIGEST_PROMPT | Weekly summary | Text (200 word cap for free tier) |
| `reid_tiebreaker()` | REID_TIEBREAKER_PROMPT | Uncertain Re-ID match | same_person, confidence, reasoning |

### Structured Response Contract
All vision functions return a standardised format:
```json
{
  "change_detected": true,
  "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "description": "one sentence, what is happening",
  "action": "recommended action for building owner",
  "objects_detected": ["person", "vehicle"]
}
```
NO_CHANGE short-circuit: `{"change_detected": false}` — skips DB write entirely.

### Structured Analysis Schema Validation
`analyse_frame_structured()` validates against controlled vocabulary:
- event_type: person_entering|person_leaving|loitering|vehicle|crowd|fight|unknown
- threat_level: LOW|MEDIUM|HIGH|EMERGENCY|CRITICAL
- confidence: 0.0–1.0 (discarded if < 0.6)
- If validation fails → retries once → falls back to safe default

### Rate Limiting

| Level | Limit | Scope |
|-------|-------|-------|
| Global (`_rate_limit()`) | 1 call per 8 seconds | All cameras combined |
| Per-incident throttle | 1 call per 15 seconds | Single incident |
| Incident builder | 1 call per 120 seconds | Single camera |

### NO_CHANGE Short-Circuit
All Gemini prompts include a NO_CHANGE fallback. If scene is unchanged,
Gemini returns `{"change_detected": false}`. Pipeline then:
1. Records timestamp (extends skip window in incident builder)
2. Skips all downstream processing (Re-ID, cross-camera, alerts, DB)
3. Saves ~30% additional Gemini costs

---

## File: reid_engine.py

### Approach: pgvector Cosine Similarity

```
Step 1: Gemini extracts person appearance description from frame
Step 2: Re-ID engine calls identify() with frame crop + location + user
Step 3: pgvector cosine similarity in Postgres
  SELECT person_uid FROM persons
  ORDER BY embedding <-> %s LIMIT 5
  > 0.85  → confident match → return existing ID
  0.5–0.72 → uncertain → Gemini tiebreaker
  < 0.5   → new person → mint new ID
Step 4 (uncertain zone):
  Gemini reid_tiebreaker() compares appearance descriptions
```

### Functions
```python
async def identify(db, frame, person_result, location_id, user_id) -> tuple[str, float]
    # Returns: (person_uid, confidence)
    # Creates new person if no match found
```

Note: BoxMOT (FastReID backend) is disabled in requirements.txt
(commented out with "disabled due to numpy conflict").
The embedding column (vector(512)) exists in the persons table schema
but is populated solely by Gemini appearance descriptions until
a suitable embedding model is integrated.

---

## File: query_engine.py

### Flow
```
User query → parse intent → SQL filter → fetch events → Gemini synthesis → answer
```

### Functions
```python
async def parse_query_intent(question: str) -> QueryIntent
async def build_sql_filter(intent: QueryIntent) -> str
async def fetch_matching_events(filter: str) -> list
async def synthesise_answer(question: str, events: list, analyses: list) -> str
```

### Query Types
- Appearance ("who wore red?")
- Object in hand ("what was person 7 holding?")
- Scene state ("are all gates locked?")
- Behaviour ("did anyone run?")
- Cross-camera ("track person 7 across all cameras")
- Timeline ("what happened 2pm-6pm?")

---

## Dependencies
- `google-cloud-aiplatform==1.71.0` (Vertex AI Gemini SDK)
- `pgvector==0.2.4` (vector similarity)
- `opencv-python` (frame decoding for Re-ID crops)
- `pydantic-settings` (centralized config via backend/config.py)

## Called By
- backend/core/pipeline.py (analyse_frame_structured, analyse_frame_with_second_pass, make_incident_decision)
- backend/core/pipeline_v2.py (via CameraPipeline)
- backend/api/queries.py (query_engine)
- backend/analytics/digest_generator.py (daily/weekly digest)