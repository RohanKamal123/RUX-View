# CONTEXT.md — AI Module
# Module: backend/ai/
# Sprint: 1.4 (ai_client.py), 3.3 (reid_engine.py), 5.2 (query_engine.py)
# Purpose: All AI/ML operations

---

## What This Module Does

Four files handling all AI operations:

1. **ai_client.py** — Gemini 2.0 Flash unified client (vision + reasoning + queries + digests)
2. **groq_client.py** — Groq API for ultra-fast Bangla transcription (replaces OpenAI Whisper)
3. **reid_engine.py** — BoxMOT FastReID + pgvector person re-identification
4. **query_engine.py** — Natural language query processing

---

## File: ai_client.py (Sprint 1.4)

Single file for ALL Gemini 2.0 Flash operations. NOT split into gemma_client.py + gemini_client.py.

### Functions

```python
# Vision Analysis (fast — used during incidents)
async def analyse_frame(jpeg_bytes: bytes) -> dict
    # Returns: {persons: [{gender, age_estimate, clothing, hand_objects, carried_items, action, bbox_normalized}], person_count, scene_alerts, vehicles}

# Vision Analysis (detailed — for NL queries)
async def analyse_frame_detailed(jpeg_bytes: bytes) -> dict
    # Returns: exhaustive clothing/accessories/position data

# Shop Entry Analysis
async def analyse_shop_entry(jpeg_bytes: bytes) -> dict
    # Returns: {gender, age_group, carried_items, group_size, confidence}

# Incident Decision
async def make_incident_decision(timeline: list, context: dict) -> dict
    # Returns: {threat_level, alert_message, action, reasoning, person_ids, follow_up}

# Query Answering
async def answer_query(question: str, events: list, analyses: list) -> str
    # Returns: plain text answer with person IDs and timestamps

# Scene State Query
async def answer_scene_state(question: str, world_state: dict) -> str
    # Returns: answer about gate/door status

# Daily/Weekly Digest
async def generate_daily_digest(events: dict, tier: str) -> str
async def generate_weekly_digest(events: dict, tier: str) -> str
    # Returns: Telegram-ready text (max 200 words for free tier)

# Re-ID Tiebreaker (uncertainty zone 0.5-0.72)
async def reid_tiebreaker(desc_a: str, desc_b: str, time_gap: int) -> dict
    # Returns: {same_person: bool, confidence: float, reasoning: str}
```

### Stack
```python
import vertexai
from vertexai.generative_models import GenerativeModel, Part

vertexai.init(project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_REGION)
model = GenerativeModel("gemini-2.0-flash")
# Uses Application Default Credentials (ADC) — no API key needed
```

### Key Decisions
- **D001** — Gemini 2.0 Flash unified (NOT split Gemma/Gemini)
- **D026** — All calls async (await)

---

## File: groq_client.py (Sprint 1.4)

```python
async def transcribe_audio(audio_bytes: bytes) -> str
    # Uses Groq API (whisper-large-v3-turbo) — replaces OpenAI Whisper
    # Returns: Bangla transcript text
```

### Key Decisions
- **D003** — Groq API (replaces OpenAI Whisper for V1 — 10-100x faster inference)
- **D020** — Transcripts stored 1-3 days only (privacy)

---

## File: reid_engine.py (Sprint 3.3)

### 3-Tier Matching Cascade
1. **Embedding similarity** (pgvector cosine, threshold 0.73)
2. **Appearance string match** (Jaccard similarity on Gemini descriptions)
3. **Gemini tiebreaker** (ai_client.reid_tiebreaker() for 0.50-0.72 range)

### Functions
```python
async def get_or_create_person(jpeg_crop: bytes, camera_id: str, location_id: str, appearance_str: str, timestamp: datetime) -> PersonMatch
async def embed_person_crop(jpeg_crop: bytes) -> np.ndarray  # shape: (512,)
```

### Key Decisions
- **D007** — BoxMOT (FastReID) replaces torchreid
- **D022** — pgvector for embedding storage

---

## File: query_engine.py (Sprint 5.2)

### Flow
User query → parse intent → SQL filter → fetch events → Gemini synthesis → answer

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
- google-cloud-aiplatform (Vertex AI Gemini — replaces google-generativeai)
- groq (Groq API — replaces OpenAI Whisper)
- boxmot (FastReID backend)
- pgvector (embedding similarity)
- database.py (persons table)
- pydantic-settings (centralized config via backend/config.py)

## Called By
- backend/core/pipeline.py
- backend/api/queries.py
- backend/analytics/digest_generator.py
