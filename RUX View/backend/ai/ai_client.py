"""
ai_client.py — Vision OS AI Client (Gemini 2.0 Flash)

Unified client for ALL Gemini operations:
- Vision analysis (fast + detailed)
- Shop entry analysis
- Incident decision-making
- NL query answering
- Scene state queries
- Daily/weekly digest generation
- Re-ID tiebreaker

All functions are async. Uses google-generativeai SDK.
"""

import json
import logging

import google.generativeai as genai

from backend.config import settings

logger = logging.getLogger(__name__)

# ── Module-level cache ─────────────────────────────────────────
_model = None


def _get_model():
    """Lazy-init Gemini model singleton."""
    global _model
    if _model is None:
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-2.0-flash-exp")
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
        model = _get_model()
        response = await model.generate_content_async(
            [LIVE_VISION_PROMPT, {"mime_type": "image/jpeg", "data": jpeg_bytes}]
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
            [QUERY_PROMPT, {"mime_type": "image/jpeg", "data": jpeg_bytes}]
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
            [SHOP_ENTRY_PROMPT, {"mime_type": "image/jpeg", "data": jpeg_bytes}]
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
