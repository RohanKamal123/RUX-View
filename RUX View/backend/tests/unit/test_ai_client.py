"""
test_ai_client.py — Unit tests for Vision OS AI client.

Tests Gemini vision analysis, incident decision, query answering,
digest generation, Re-ID tiebreaker, and Groq transcription.
Uses mocking to avoid real API calls.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_gemini_model():
    """Mock the Gemini GenerativeModel."""
    with patch("backend.ai.ai_client._get_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock()
        mock_get_model.return_value = mock_model
        yield mock_model


@pytest.fixture
def mock_groq_client():
    """Mock the Groq async client."""
    with patch("backend.ai.groq_client._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock()
        mock_get_client.return_value = mock_client
        yield mock_client


# ── Test: analyse_frame ───────────────────────────────────────


@pytest.mark.asyncio
async def test_analyse_frame_returns_required_fields(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that analyse_frame returns all required fields."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "persons": [
                {
                    "gender": "male",
                    "age_estimate": 30,
                    "clothing": "blue shirt",
                    "hand_objects": [],
                    "carried_items": [],
                    "action": "walking",
                    "anomaly_signals": [],
                    "bbox_normalized": [0.1, 0.2, 0.3, 0.4],
                }
            ],
            "person_count": 1,
            "scene_alerts": [],
            "vehicles": [],
            "gates_visible": {},
        }
    )

    from backend.ai.ai_client import analyse_frame

    result = await analyse_frame(sample_jpeg_bytes)
    assert "persons" in result
    assert "person_count" in result
    assert "scene_alerts" in result
    assert "vehicles" in result
    assert result["person_count"] == 1
    assert len(result["persons"]) == 1
    assert result["persons"][0]["gender"] == "male"


@pytest.mark.asyncio
async def test_analyse_frame_handles_invalid_response(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that analyse_frame handles invalid JSON gracefully."""
    mock_gemini_model.generate_content_async.return_value.text = "Not JSON at all"

    from backend.ai.ai_client import analyse_frame

    result = await analyse_frame(sample_jpeg_bytes)
    assert "persons" in result
    assert result["person_count"] == 0


# ── Test: analyse_frame_detailed ──────────────────────────────


@pytest.mark.asyncio
async def test_analyse_frame_detailed_prompt_parse(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that detailed analysis parses correctly."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "persons": [
                {
                    "gender": "female",
                    "age_estimate": 25,
                    "clothing": {
                        "top": "red t-shirt",
                        "bottom": "black jeans",
                        "shoes": "white sneakers",
                        "accessories": ["watch"],
                    },
                    "hand_objects": ["phone"],
                    "carried_items": ["handbag"],
                    "action": "standing",
                    "body_language": "relaxed",
                    "face_direction": "looking at camera",
                    "position": "near front door",
                    "bbox_normalized": [0.2, 0.3, 0.4, 0.5],
                }
            ],
            "scene": {
                "gates": {"main_gate": "open"},
                "doors": {"front_door": "closed"},
                "vehicles": [],
                "unattended_objects": [],
                "lighting": "daylight",
                "weather_hint": "sunny",
            },
            "anomalies": [],
        }
    )

    from backend.ai.ai_client import analyse_frame_detailed

    result = await analyse_frame_detailed(sample_jpeg_bytes)
    assert "persons" in result
    assert "scene" in result
    assert result["persons"][0]["clothing"]["top"] == "red t-shirt"
    assert result["scene"]["lighting"] == "daylight"


# ── Test: analyse_shop_entry ──────────────────────────────────


@pytest.mark.asyncio
async def test_shop_entry_returns_demographics(mock_gemini_model, sample_jpeg_bytes):
    """Test that shop entry analysis returns demographics."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "gender": "male",
            "age_group": "30s",
            "carried_items": ["bag"],
            "group_size": 1,
            "confidence": 0.92,
        }
    )

    from backend.ai.ai_client import analyse_shop_entry

    result = await analyse_shop_entry(sample_jpeg_bytes)
    assert result["gender"] == "male"
    assert result["age_group"] == "30s"
    assert result["group_size"] == 1
    assert result["confidence"] == 0.92


# ── Test: make_incident_decision ──────────────────────────────


@pytest.mark.asyncio
async def test_incident_decision_parse(mock_gemini_model):
    """Test that incident decision parses correctly."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "threat_level": "HIGH",
            "alert_message": "Intruder detected at front gate",
            "action": "TELEGRAM_PHOTO",
            "reasoning": "Unknown person climbing gate at night",
            "person_ids": ["PERSON_007"],
            "follow_up": "Check front gate footage",
        }
    )

    from backend.ai.ai_client import make_incident_decision

    result = await make_incident_decision(
        timeline=[{"time": "10:00", "action": "climbing"}],
        context={
            "camera_name": "Front Gate",
            "camera_mode": "outdoor",
            "timestamp": "2026-04-25T22:00:00",
            "location_type": "residential",
            "is_business_hours": False,
            "duration": 30,
            "reid_result": "new_person",
            "is_known": False,
            "label": "unknown",
            "audio_context": "none",
            "history": [],
        },
    )
    assert result["threat_level"] == "HIGH"
    assert result["action"] == "TELEGRAM_PHOTO"
    assert "PERSON_007" in result["person_ids"]


# ── Test: answer_query ────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_answer_format(mock_gemini_model):
    """Test that query answering returns text."""
    mock_gemini_model.generate_content_async.return_value.text = (
        "The person in the red shirt was seen at 10:30 AM near the front door. "
        "Person ID: PERSON_003."
    )

    from backend.ai.ai_client import answer_query

    result = await answer_query(
        question="Who wore a red shirt?",
        events=[{"id": 1, "incident_id": "INC_001"}],
        analyses=[{"persons": [{"clothing": "red shirt"}]}],
    )
    assert isinstance(result, str)
    assert "PERSON_003" in result


# ── Test: answer_scene_state ──────────────────────────────────


@pytest.mark.asyncio
async def test_scene_state_query(mock_gemini_model):
    """Test that scene state query returns text."""
    mock_gemini_model.generate_content_async.return_value.text = (
        "The front gate is currently open."
    )

    from backend.ai.ai_client import answer_scene_state

    result = await answer_scene_state(
        question="Is the front gate open?",
        world_state={"gates": {"front_gate": "open"}},
    )
    assert isinstance(result, str)
    assert "open" in result.lower()


# ── Test: Digest ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_digest_under_200_words_free_tier(mock_gemini_model):
    """Test that free tier digest is limited to 200 words."""
    long_text = "word " * 300
    mock_gemini_model.generate_content_async.return_value.text = long_text

    from backend.ai.ai_client import generate_daily_digest

    result = await generate_daily_digest(
        events={"total": 5, "high_threat": 1},
        tier="free",
    )
    words = result.split()
    assert len(words) <= 200


@pytest.mark.asyncio
async def test_digest_business_tier_no_limit(mock_gemini_model):
    """Test that business tier digest is not limited."""
    long_text = "word " * 300
    mock_gemini_model.generate_content_async.return_value.text = long_text

    from backend.ai.ai_client import generate_daily_digest

    result = await generate_daily_digest(
        events={"total": 5, "high_threat": 1},
        tier="business",
    )
    words = result.split()
    assert len(words) > 200  # Not truncated


# ── Test: Re-ID Tiebreaker ────────────────────────────────────


@pytest.mark.asyncio
async def test_reid_tiebreaker_returns_match_bool(mock_gemini_model):
    """Test that Re-ID tiebreaker returns structured result."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "same_person": True,
            "confidence": 0.85,
            "reasoning": "Both wearing red shirt and black jeans",
        }
    )

    from backend.ai.ai_client import reid_tiebreaker

    result = await reid_tiebreaker(
        desc_a="Person in red shirt, black jeans",
        desc_b="Person in red top, dark pants",
        time_gap=120,
    )
    assert "same_person" in result
    assert "confidence" in result
    assert "reasoning" in result
    assert result["same_person"] is True
    assert result["confidence"] == 0.85


# ── Test: analyse_frame_structured ────────────────────────────


@pytest.mark.asyncio
async def test_analyse_frame_structured_returns_valid_schema(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that analyse_frame_structured returns valid structured JSON."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "event_type": "person_entering",
            "threat_level": "LOW",
            "confidence": 0.85,
            "description": "A person is entering through the front gate",
            "action_required": False,
            "subject_count": 1,
            "subject_description": "male in blue shirt",
        }
    )

    from backend.ai.ai_client import analyse_frame_structured

    result = await analyse_frame_structured(sample_jpeg_bytes)
    assert result["event_type"] == "person_entering"
    assert result["threat_level"] == "LOW"
    assert result["confidence"] == 0.85
    assert result["action_required"] is False
    assert result["subject_count"] == 1


@pytest.mark.asyncio
async def test_analyse_frame_structured_discards_low_confidence(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that confidence < 0.6 returns empty dict (silent discard)."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "event_type": "person_entering",
            "threat_level": "LOW",
            "confidence": 0.45,
            "description": "A person is entering",
            "action_required": False,
            "subject_count": 1,
            "subject_description": "male",
        }
    )

    from backend.ai.ai_client import analyse_frame_structured

    result = await analyse_frame_structured(sample_jpeg_bytes)
    assert result == {}  # Silent discard


@pytest.mark.asyncio
async def test_analyse_frame_structured_retries_on_invalid(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that invalid schema triggers a retry, then uses fallback."""
    # First call returns invalid, second returns valid
    mock_gemini_model.generate_content_async.side_effect = [
        MagicMock(text="Not valid JSON at all"),
        MagicMock(
            text=json.dumps(
                {
                    "event_type": "vehicle",
                    "threat_level": "MEDIUM",
                    "confidence": 0.72,
                    "description": "A vehicle is approaching the gate",
                    "action_required": True,
                    "subject_count": 1,
                    "subject_description": "white sedan",
                }
            )
        ),
    ]

    from backend.ai.ai_client import analyse_frame_structured

    result = await analyse_frame_structured(sample_jpeg_bytes)
    assert result["event_type"] == "vehicle"
    assert result["confidence"] == 0.72


@pytest.mark.asyncio
async def test_analyse_frame_structured_fallback_after_retry(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that both attempts failing returns safe default."""
    mock_gemini_model.generate_content_async.side_effect = [
        MagicMock(text="Not JSON"),
        MagicMock(text="Still not JSON"),
    ]

    from backend.ai.ai_client import analyse_frame_structured

    result = await analyse_frame_structured(sample_jpeg_bytes)
    assert result["event_type"] == "unknown"
    assert result["threat_level"] == "LOW"
    assert result["confidence"] == 0.0
    assert result["action_required"] is False


@pytest.mark.asyncio
async def test_analyse_frame_structured_validates_controlled_vocab(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that invalid event_type triggers retry."""
    mock_gemini_model.generate_content_async.return_value.text = json.dumps(
        {
            "event_type": "invalid_type_here",
            "threat_level": "LOW",
            "confidence": 0.9,
            "description": "test",
            "action_required": False,
            "subject_count": 0,
            "subject_description": "",
        }
    )

    from backend.ai.ai_client import analyse_frame_structured

    result = await analyse_frame_structured(sample_jpeg_bytes)
    # Should retry, but mock returns same invalid — falls to safe default
    assert result["event_type"] == "unknown"


# ── Test: Groq Transcription ──────────────────────────────────


@pytest.mark.asyncio
async def test_groq_transcription(mock_groq_client, sample_audio_bytes):
    """Test that Groq transcription returns text."""
    mock_groq_client.audio.transcriptions.create.return_value = "আমার সোনার বাংলা"

    from backend.ai.groq_client import transcribe_audio

    result = await transcribe_audio(sample_audio_bytes)
    assert isinstance(result, str)
    assert len(result) > 0


# ── Test: Error Handling ──────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_response_handled_gracefully(
    mock_gemini_model, sample_jpeg_bytes
):
    """Test that invalid Gemini responses are handled gracefully."""
    mock_gemini_model.generate_content_async.side_effect = Exception("API Error")

    from backend.ai.ai_client import analyse_frame

    result = await analyse_frame(sample_jpeg_bytes)
    assert "persons" in result
    assert result["person_count"] == 0
    assert len(result["scene_alerts"]) > 0


@pytest.mark.asyncio
async def test_groq_error_handled(mock_groq_client, sample_audio_bytes):
    """Test that Groq errors are propagated."""
    mock_groq_client.audio.transcriptions.create.side_effect = Exception("API Error")

    from backend.ai.groq_client import transcribe_audio

    with pytest.raises(Exception):
        await transcribe_audio(sample_audio_bytes)
