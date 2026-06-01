"""
ai_client.py — Vision OS AI Client (Vertex AI Gemini)

Unified client for ALL Gemini operations via Vertex AI:
- Vision analysis (fast + detailed)
- Structured JSON analysis (with quality gates)
- Shop entry analysis
- Incident decision-making
- NL query answering
- Scene state queries
- Daily/weekly digest generation
- Re-ID tiebreaker

All functions are async. Uses google-cloud-aiplatform (vertexai) SDK.
Authentication uses Application Default Credentials (ADC) — no API key needed.
"""

import asyncio
import json
import logging
import time

import vertexai
from vertexai.generative_models import GenerativeModel, Part

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Module-level cache ─────────────────────────────────────────
_model = None
_vertex_initialized = False

# ── Global rate limiter: max 1 Gemini call per 5 seconds ──────
_last_gemini_call: float = 0.0
_gemini_lock = asyncio.Lock()
_GEMINI_MIN_INTERVAL = 8.0  # seconds


def _init_vertex():
    """Initialize Vertex AI SDK once (singleton)."""
    global _vertex_initialized
    if not _vertex_initialized:
        project = settings.google_cloud_project or "rux-view-497104"
        location = settings.google_cloud_region or "us-central1"
        logger.info(
            "Initializing Vertex AI: project=%s, location=%s",
            project, location,
        )
        vertexai.init(project=project, location=location)
        _vertex_initialized = True


async def _rate_limit() -> bool:
    """Global rate limiter — max 1 Gemini call per 5 seconds.

    If the minimum interval has elapsed, returns True immediately.
    Otherwise waits up to 5s for the lock, then checks again.
    If still too soon, returns False — caller should skip/fallback.

    Returns:
        True if caller may proceed, False if rate-limited.
    """
    global _last_gemini_call
    async with _gemini_lock:
        now = time.monotonic()
        elapsed = now - _last_gemini_call
        if elapsed >= _GEMINI_MIN_INTERVAL:
            _last_gemini_call = now
            return True
        # Wait for the remaining time, then retry once
        wait_time = _GEMINI_MIN_INTERVAL - elapsed
        logger.info("Rate limit: waiting %.1fs before Gemini call", wait_time)
        await asyncio.sleep(wait_time)
        # Retry check after waiting
        now = time.monotonic()
        elapsed = now - _last_gemini_call
        if elapsed >= _GEMINI_MIN_INTERVAL:
            _last_gemini_call = now
            return True
        # Still rate-limited — skip
        logger.warning("Rate limit hit: skipping Gemini call (only %.1fs since last)", elapsed)
        return False


def _get_model():
    """Lazy-init Vertex AI Gemini model singleton."""
    global _model
    if _model is None:
        _init_vertex()
        _model = GenerativeModel("gemini-2.0-flash")
    return _model


# ── Helpers ────────────────────────────────────────────────────


def _parse_json(text: str, fallback: dict) -> dict:
    """Safely parse JSON from Gemini response with fallback."""
    if not text or not text.strip():
        logger.warning("Empty Gemini response — using fallback")
        return fallback

    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (possibly with language hint)
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        # Remove closing fence
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        elif "```" in cleaned:
            cleaned = cleaned[: cleaned.rfind("```")].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse Gemini JSON: %s — text=%r", exc, cleaned[:200])
        return fallback


def _truncate_text(text: str, max_words: int = 200) -> str:
    """Truncate text to max_words, preserving whole words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


# ── Structured Analysis Schema ─────────────────────────────────

STRUCTURED_ANALYSIS_SCHEMA = {
    "event_type": "person_entering|person_leaving|loitering|vehicle|crowd|fight|unknown",
    "threat_level": "LOW|MEDIUM|HIGH|EMERGENCY",
    "confidence": "0.0-1.0",
    "description": "One clear sentence describing exactly what happened",
    "action_required": "true/false",
    "subject_count": 0,
    "subject_description": "brief description or empty string",
}

STRUCTURED_ANALYSIS_PROMPT = """Analyse this CCTV frame. Return ONLY valid JSON with EXACTLY these keys and controlled vocabulary. No explanation. No markdown.

{
  "event_type": "person_entering|person_leaving|loitering|vehicle|crowd|fight|unknown",
  "threat_level": "LOW|MEDIUM|HIGH|EMERGENCY",
  "confidence": 0.0-1.0,
  "description": "One clear sentence describing exactly what happened",
  "action_required": true/false,
  "subject_count": 0,
  "subject_description": "brief description or empty string"
}

Use ONLY the exact values listed for event_type and threat_level. confidence must be a float between 0.0 and 1.0."""

STRUCTURED_ANALYSIS_FALLBACK = {
    "event_type": "unknown",
    "threat_level": "LOW",
    "confidence": 0.0,
    "description": "No analysis available",
    "action_required": False,
    "subject_count": 0,
    "subject_description": "",
}

VALID_EVENT_TYPES = {"person_entering", "person_leaving", "loitering", "vehicle", "crowd", "fight", "unknown"}
VALID_THREAT_LEVELS = {"LOW", "MEDIUM", "HIGH", "EMERGENCY"}


def _validate_structured_result(result: dict) -> bool:
    """Validate that a structured result matches the required schema and controlled vocabulary."""
    required_keys = {"event_type", "threat_level", "confidence", "description", "action_required", "subject_count", "subject_description"}
    if not all(k in result for k in required_keys):
        logger.warning("Structured result missing keys: %s", required_keys - set(result.keys()))
        return False
    if result.get("event_type") not in VALID_EVENT_TYPES:
        logger.warning("Invalid event_type: %s", result.get("event_type"))
        return False
    if result.get("threat_level") not in VALID_THREAT_LEVELS:
        logger.warning("Invalid threat_level: %s", result.get("threat_level"))
        return False
    confidence = result.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
        logger.warning("Invalid confidence value: %s", confidence)
        return False
    if not isinstance(result.get("action_required"), bool):
        logger.warning("action_required must be boolean, got: %s", type(result.get("action_required")))
        return False
    if not isinstance(result.get("subject_count"), int) or result["subject_count"] < 0:
        logger.warning("subject_count must be non-negative int, got: %s", result.get("subject_count"))
        return False
    return True


async def analyse_frame_structured(jpeg_bytes: bytes) -> dict:
    """Analyse a CCTV frame and return structured JSON output.

    Forces Gemini to return a controlled-vocabulary structured result.
    - If confidence < 0.6, returns empty dict (silent discard).
    - If schema validation fails, retries once, then returns safe default.
    - If Gemini returns invalid JSON, retries once, then returns safe default.

    Returns:
        dict with keys: event_type, threat_level, confidence, description,
                        action_required, subject_count, subject_description
        OR empty dict {} if confidence < 0.6 (silent discard).
    """
    try:
        # ── Global rate limit check ────────────────────────────
        if not await _rate_limit():
            logger.warning("Rate limited: skipping analyse_frame_structured")
            return dict(STRUCTURED_ANALYSIS_FALLBACK)

        model = _get_model()

        # First attempt
        response = await model.generate_content_async(
            [STRUCTURED_ANALYSIS_PROMPT, Part.from_data(data=jpeg_bytes, mime_type="image/jpeg")]
        )
        result = _parse_json(response.text, {})

        # Validate schema
        if result and _validate_structured_result(result):
            # Check confidence threshold
            if result.get("confidence", 0.0) < 0.6:
                logger.debug("Frame analysis discarded: confidence %.2f < 0.6", result.get("confidence", 0.0))
                return {}  # Silent discard
            return result

        # First attempt failed validation — retry once
        logger.warning("Structured analysis failed validation, retrying once...")
        if not await _rate_limit():
            logger.warning("Rate limited: skipping retry for analyse_frame_structured")
            return dict(STRUCTURED_ANALYSIS_FALLBACK)
        response = await model.generate_content_async(
            [STRUCTURED_ANALYSIS_PROMPT, Part.from_data(data=jpeg_bytes, mime_type="image/jpeg")]
        )
        result = _parse_json(response.text, {})

        if result and _validate_structured_result(result):
            if result.get("confidence", 0.0) < 0.6:
                logger.debug("Frame analysis discarded (retry): confidence %.2f < 0.6", result.get("confidence", 0.0))
                return {}
            return result

        # Both attempts failed — use safe default
        logger.warning("Structured analysis failed after retry, using safe default")
        return dict(STRUCTURED_ANALYSIS_FALLBACK)

    except Exception as exc:
        logger.error("analyse_frame_structured failed: %s", exc, exc_info=True)
        return dict(STRUCTURED_ANALYSIS_FALLBACK)


# ── Prompts ────────────────────────────────────────────────────

LIVE_VISION_PROMPT = """Analyse this CCTV frame quickly. Return JSON only.
No explanation. No markdown.

{
  "persons": [{
    "gender": "male/female/unknown",
    "age_estimate": 28,
    "clothing": "red shirt, black jeans",
    "hand_objects": ["phone"],
    "carried_items": ["backpack"],
    "action": "walking/running/standing/crouching/climbing",
    "anomaly_signals": [],
    "bbox_normalized": [0.2, 0.1, 0.45, 0.9]
  }],
  "person_count": 1,
  "scene_alerts": [],
  "vehicles": [],
  "gates_visible": {}
}"""

QUERY_PROMPT = """Analyse this CCTV frame in extreme detail.
This data answers user queries like
"who wore red?" or "what was in their hand?"
Be obsessively descriptive. Return JSON only.

{
  "persons": [{
    "gender": "male/female/unknown",
    "age_estimate": 28,
    "clothing": {
      "top": "exact color and garment type",
      "bottom": "exact color and type",
      "shoes": "description or unknown",
      "accessories": ["cap", "watch", "glasses"]
    },
    "hand_objects": ["mobile phone", "keys"],
    "carried_items": ["black backpack"],
    "action": "detailed action description",
    "body_language": "relaxed/nervous/aggressive/hurried",
    "face_direction": "looking at camera/away/down",
    "position": "description relative to doors/gates/objects",
    "bbox_normalized": [0.2, 0.1, 0.45, 0.9]
  }],
  "scene": {
    "gates": {"gate_1": "open/closed/unknown"},
    "doors": {"front_door": "open/closed/unknown"},
    "vehicles": ["white sedan parked left"],
    "unattended_objects": ["black bag near gate"],
    "lighting": "daylight/night/artificial/IR",
    "weather_hint": "sunny/overcast/rainy/dark"
  },
  "anomalies": []
}"""

SHOP_ENTRY_PROMPT = """Analyse this CCTV frame for shop entry detection.
Return JSON only. No explanation. No markdown.

{
  "gender": "male/female/unknown",
  "age_group": "child/teen/20s/30s/40s/50s/60+/unknown",
  "carried_items": ["bag", "umbrella"],
  "group_size": 1,
  "confidence": 0.95
}"""

INCIDENT_DECISION_PROMPT = """You are a CCTV security analyst for a property in Bangladesh.

Camera: {camera_name}
Mode: {camera_mode}
Time: {timestamp}
Location type: {location_type}
Business hours: {is_business_hours}

Incident timeline (vision observations):
{timeline}

Duration: {duration}s
Re-ID result: {reid_result}
Known person: {is_known} ({label})
Audio context: {audio_context}
Recent history (last 10 events this camera): {history}

Return JSON only:
{{
  "threat_level": "LOW/MEDIUM/HIGH",
  "alert_message": "one sentence, plain text, no markdown",
  "action": "LOG_ONLY/TELEGRAM_TEXT/TELEGRAM_PHOTO/EMERGENCY",
  "reasoning": "brief explanation",
  "person_ids": ["PERSON_007"],
  "follow_up": "any recommended action for owner"
}}"""

QUERY_ANSWER_PROMPT = """You are a CCTV security analyst for a property in Bangladesh.

User question: {question}

Recent events:
{events}

Vision analyses of relevant frames:
{analyses}

Answer the question in plain text. Reference person IDs and timestamps where relevant.
Be concise but thorough."""

SCENE_STATE_PROMPT = """You are a CCTV security analyst for a property in Bangladesh.

User question: {question}

Current world state:
{world_state}

Answer the question about gate/door status or scene state in plain text.
Be concise."""

DAILY_DIGEST_PROMPT = """You are a CCTV security analyst generating a daily digest for a property owner in Bangladesh.

Events today:
{events}

Generate a concise daily digest. {word_limit}
Focus on: total incidents, threat levels, notable events, and any recommended actions.
Plain text only, no markdown."""

WEEKLY_DIGEST_PROMPT = """You are a CCTV security analyst generating a weekly digest for a property owner in Bangladesh.

Events this week:
{events}

Generate a concise weekly digest. {word_limit}
Focus on: total incidents, threat levels, notable events, trends, and any recommended actions.
Plain text only, no markdown."""

REID_TIEBREAKER_PROMPT = """You are a Re-ID (Re-Identification) analyst for CCTV.

Description A: {desc_a}
Description B: {desc_b}
Time gap between sightings: {time_gap}s

Determine if these descriptions refer to the same person.
Return JSON only:
{{
  "same_person": true/false,
  "confidence": 0.85,
  "reasoning": "brief explanation"
}}"""


SECOND_PASS_PROMPT = """You are a CCTV security analyst. You have received a text description
of a scene that was extracted from a camera frame by a vision model.

Scene description:
{vision_summary}

Analyse this description and provide a final security verdict.
Return JSON only. No explanation. No markdown.

{{
  "threat_level": "LOW/MEDIUM/HIGH",
  "alert_message": "one sentence actionable alert for the property owner",
  "action": "LOG_ONLY/TELEGRAM_TEXT/TELEGRAM_PHOTO/EMERGENCY",
  "reasoning": "brief explanation of why this verdict was reached",
  "person_ids": [],
  "follow_up": "any recommended action for the owner"
}}"""


async def analyse_frame_with_second_pass(jpeg_bytes: bytes) -> dict:
    """Dual-layer AI analysis: vision → text analysis → final verdict.

    Layer 1: Gemini vision analyses the JPEG frame → extracts persons, scene, alerts.
    Layer 2: The text summary is fed to a second Gemini call that produces a
             final security verdict with actionable alert message.

    Returns:
        dict with keys from analyse_frame (persons, person_count, scene_alerts, etc.)
        PLUS: threat_level, alert_message, action, reasoning, follow_up
    """
    fallback = {
        "persons": [],
        "person_count": 0,
        "scene_alerts": [],
        "vehicles": [],
        "gates_visible": {},
        "threat_level": "LOW",
        "alert_message": "No alert",
        "action": "LOG_ONLY",
        "reasoning": "AI analysis failed",
        "person_ids": [],
        "follow_up": "",
    }
    try:
        # Layer 1: Vision analysis
        vision_result = await analyse_frame(jpeg_bytes)
        if not vision_result.get("persons") and not vision_result.get("scene_alerts"):
            # No persons or alerts — nothing to analyse further
            fallback.update(vision_result)
            fallback["threat_level"] = "LOW"
            fallback["alert_message"] = "No activity detected"
            return fallback

        # Build a text summary from the vision result
        summary_parts = []
        summary_parts.append(f"Person count: {vision_result.get('person_count', 0)}")
        for p in vision_result.get("persons", []):
            summary_parts.append(
                f"Person: gender={p.get('gender','unknown')}, "
                f"age={p.get('age_estimate','unknown')}, "
                f"clothing={p.get('clothing','unknown')}, "
                f"action={p.get('action','unknown')}, "
                f"hand_objects={p.get('hand_objects',[])}, "
                f"carried_items={p.get('carried_items',[])}"
            )
        if vision_result.get("scene_alerts"):
            summary_parts.append(f"Scene alerts: {', '.join(vision_result['scene_alerts'])}")
        if vision_result.get("vehicles"):
            summary_parts.append(f"Vehicles: {vision_result['vehicles']}")
        if vision_result.get("gates_visible"):
            summary_parts.append(f"Gates: {vision_result['gates_visible']}")

        vision_summary = "\n".join(summary_parts)

        # Layer 2: Text analysis → final verdict
        model = _get_model()
        prompt = SECOND_PASS_PROMPT.format(vision_summary=vision_summary)
        response = await model.generate_content_async(prompt)
        verdict = _parse_json(response.text, {})

        # Merge vision result with verdict
        result = dict(vision_result)
        result["threat_level"] = verdict.get("threat_level", fallback["threat_level"])
        result["alert_message"] = verdict.get("alert_message", fallback["alert_message"])
        result["action"] = verdict.get("action", fallback["action"])
        result["reasoning"] = verdict.get("reasoning", fallback["reasoning"])
        result["person_ids"] = verdict.get("person_ids", fallback["person_ids"])
        result["follow_up"] = verdict.get("follow_up", fallback["follow_up"])

        for key in fallback:
            result.setdefault(key, fallback[key])
        return result

    except Exception as exc:
        logger.error("analyse_frame_with_second_pass failed: %s", exc, exc_info=True)
        return fallback


# ── Vision Analysis (fast — used during incidents) ─────────────


async def analyse_frame(jpeg_bytes: bytes) -> dict:
    """Analyse a CCTV frame quickly for incident processing.

    Returns:
        dict with keys: persons, person_count, scene_alerts, vehicles, gates_visible
    """
    fallback = {
        "persons": [],
        "person_count": 0,
        "scene_alerts": [],
        "vehicles": [],
        "gates_visible": {},
    }
    try:
        # ── Global rate limit check ────────────────────────────
        if not await _rate_limit():
            logger.warning("Rate limited: skipping analyse_frame")
            return fallback

        model = _get_model()
        response = await model.generate_content_async(
            [LIVE_VISION_PROMPT, Part.from_data(data=jpeg_bytes, mime_type="image/jpeg")]
        )
        result = _parse_json(response.text, fallback)
        # Ensure all required keys exist
        for key in fallback:
            result.setdefault(key, fallback[key])
        return result
    except Exception as exc:
        logger.error("analyse_frame failed: %s", exc, exc_info=True)
        fallback["scene_alerts"].append(f"AI analysis error: {exc}")
        return fallback


# ── Vision Analysis (detailed — for NL queries) ────────────────


async def analyse_frame_detailed(jpeg_bytes: bytes) -> dict:
    """Analyse a CCTV frame in extreme detail for natural language queries.

    Returns:
        dict with keys: persons (detailed clothing/accessories/position), scene, anomalies
    """
    fallback = {
        "persons": [],
        "scene": {
            "gates": {},
            "doors": {},
            "vehicles": [],
            "unattended_objects": [],
            "lighting": "unknown",
            "weather_hint": "unknown",
        },
        "anomalies": [],
    }
    try:
        model = _get_model()
        response = await model.generate_content_async(
            [QUERY_PROMPT, Part.from_data(data=jpeg_bytes, mime_type="image/jpeg")]
        )
        result = _parse_json(response.text, fallback)
        for key in fallback:
            result.setdefault(key, fallback[key])
        return result
    except Exception as exc:
        logger.error("analyse_frame_detailed failed: %s", exc, exc_info=True)
        return fallback


# ── Shop Entry Analysis ────────────────────────────────────────


async def analyse_shop_entry(jpeg_bytes: bytes) -> dict:
    """Analyse a CCTV frame for shop entry demographics.

    Returns:
        dict with keys: gender, age_group, carried_items, group_size, confidence
    """
    fallback = {
        "gender": "unknown",
        "age_group": "unknown",
        "carried_items": [],
        "group_size": 0,
        "confidence": 0.0,
    }
    try:
        model = _get_model()
        response = await model.generate_content_async(
            [SHOP_ENTRY_PROMPT, Part.from_data(data=jpeg_bytes, mime_type="image/jpeg")]
        )
        result = _parse_json(response.text, fallback)
        for key in fallback:
            result.setdefault(key, fallback[key])
        return result
    except Exception as exc:
        logger.error("analyse_shop_entry failed: %s", exc, exc_info=True)
        return fallback


# ── Incident Decision ──────────────────────────────────────────


async def make_incident_decision(timeline: list, context: dict) -> dict:
    """Make a security decision based on incident timeline and context.

    Args:
        timeline: List of vision observation dicts with time/action keys.
        context: Dict with camera_name, camera_mode, timestamp, location_type,
                 is_business_hours, duration, reid_result, is_known, label,
                 audio_context, history.

    Returns:
        dict with keys: threat_level, alert_message, action, reasoning, person_ids, follow_up
    """
    fallback = {
        "threat_level": "LOW",
        "alert_message": "Unable to analyse incident",
        "action": "LOG_ONLY",
        "reasoning": "AI analysis failed",
        "person_ids": [],
        "follow_up": "",
    }
    try:
        # ── Global rate limit check ────────────────────────────
        if not await _rate_limit():
            logger.warning("Rate limited: skipping make_incident_decision")
            return fallback

        prompt = INCIDENT_DECISION_PROMPT.format(
            camera_name=context.get("camera_name", "unknown"),
            camera_mode=context.get("camera_mode", "unknown"),
            timestamp=context.get("timestamp", "unknown"),
            location_type=context.get("location_type", "unknown"),
            is_business_hours=context.get("is_business_hours", "unknown"),
            timeline=json.dumps(timeline, indent=2, default=str),
            duration=context.get("duration", 0),
            reid_result=context.get("reid_result", "unknown"),
            is_known=context.get("is_known", False),
            label=context.get("label", "unknown"),
            audio_context=context.get("audio_context", "none"),
            history=json.dumps(context.get("history", []), indent=2, default=str),
        )
        model = _get_model()
        response = await model.generate_content_async(prompt)
        result = _parse_json(response.text, fallback)
        for key in fallback:
            result.setdefault(key, fallback[key])
        return result
    except Exception as exc:
        logger.error("make_incident_decision failed: %s", exc, exc_info=True)
        return fallback


# ── Query Answering ────────────────────────────────────────────


async def answer_query(question: str, events: list, analyses: list) -> str:
    """Answer a natural language question about events and analyses.

    Returns:
        Plain text answer with person IDs and timestamps.
    """
    try:
        prompt = QUERY_ANSWER_PROMPT.format(
            question=question,
            events=json.dumps(events, indent=2, default=str),
            analyses=json.dumps(analyses, indent=2, default=str),
        )
        model = _get_model()
        response = await model.generate_content_async(prompt)
        return response.text.strip() if response.text else "No answer available."
    except Exception as exc:
        logger.error("answer_query failed: %s", exc, exc_info=True)
        return f"Unable to answer query due to an error: {exc}"


# ── Scene State Query ──────────────────────────────────────────


async def answer_scene_state(question: str, world_state: dict) -> str:
    """Answer a question about gate/door status or scene state.

    Returns:
        Plain text answer.
    """
    try:
        prompt = SCENE_STATE_PROMPT.format(
            question=question,
            world_state=json.dumps(world_state, indent=2, default=str),
        )
        model = _get_model()
        response = await model.generate_content_async(prompt)
        return response.text.strip() if response.text else "No answer available."
    except Exception as exc:
        logger.error("answer_scene_state failed: %s", exc, exc_info=True)
        return f"Unable to answer scene query due to an error: {exc}"


# ── Daily/Weekly Digest ────────────────────────────────────────


async def generate_daily_digest(events: dict, tier: str = "free") -> str:
    """Generate a daily digest of events.

    Args:
        events: Dict of event summaries.
        tier: User tier — "free" limits to 200 words, others unlimited.

    Returns:
        Telegram-ready text.
    """
    word_limit = "(max 200 words)" if tier == "free" else ""
    try:
        prompt = DAILY_DIGEST_PROMPT.format(
            events=json.dumps(events, indent=2, default=str),
            word_limit=word_limit,
        )
        model = _get_model()
        response = await model.generate_content_async(prompt)
        text = response.text.strip() if response.text else "No digest available."
        if tier == "free":
            text = _truncate_text(text, max_words=200)
        return text
    except Exception as exc:
        logger.error("generate_daily_digest failed: %s", exc, exc_info=True)
        return f"Unable to generate daily digest due to an error: {exc}"


async def generate_weekly_digest(events: dict, tier: str = "free") -> str:
    """Generate a weekly digest of events.

    Args:
        events: Dict of event summaries.
        tier: User tier — "free" limits to 200 words, others unlimited.

    Returns:
        Telegram-ready text.
    """
    word_limit = "(max 200 words)" if tier == "free" else ""
    try:
        prompt = WEEKLY_DIGEST_PROMPT.format(
            events=json.dumps(events, indent=2, default=str),
            word_limit=word_limit,
        )
        model = _get_model()
        response = await model.generate_content_async(prompt)
        text = response.text.strip() if response.text else "No digest available."
        if tier == "free":
            text = _truncate_text(text, max_words=200)
        return text
    except Exception as exc:
        logger.error("generate_weekly_digest failed: %s", exc, exc_info=True)
        return f"Unable to generate weekly digest due to an error: {exc}"


# ── Re-ID Tiebreaker ───────────────────────────────────────────


async def reid_tiebreaker(desc_a: str, desc_b: str, time_gap: int) -> dict:
    """Determine if two person descriptions refer to the same person.

    Used in the uncertainty zone (0.5-0.72) where vector similarity is ambiguous.

    Args:
        desc_a: Description of first sighting.
        desc_b: Description of second sighting.
        time_gap: Time between sightings in seconds.

    Returns:
        dict with keys: same_person (bool), confidence (float), reasoning (str)
    """
    fallback = {
        "same_person": False,
        "confidence": 0.0,
        "reasoning": "AI analysis failed",
    }
    try:
        prompt = REID_TIEBREAKER_PROMPT.format(
            desc_a=desc_a,
            desc_b=desc_b,
            time_gap=time_gap,
        )
        model = _get_model()
        response = await model.generate_content_async(prompt)
        result = _parse_json(response.text, fallback)
        for key in fallback:
            result.setdefault(key, fallback[key])
        return result
    except Exception as exc:
        logger.error("reid_tiebreaker failed: %s", exc, exc_info=True)
        return fallback
