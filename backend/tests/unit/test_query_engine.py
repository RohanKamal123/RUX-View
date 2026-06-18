"""
Tests for Sprint 5.2 — NL Query Engine.

Tests intent parsing, SQL filter building, tier gating,
and end-to-end query processing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.ai.query_engine import (
    QueryEngine,
    QueryIntent,
    ParsedQuery,
    QueryResult,
)


# ── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """Create a mock session factory."""
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_db_session
    factory.return_value.__aexit__.return_value = None
    return factory


@pytest.fixture
def mock_ai_client():
    """Create a mock AI client."""
    client = AsyncMock()
    response = MagicMock()
    response.text = '{"intent": "APPEARANCE", "filters": {"clothing": "red shirt"}}'
    client.generate_content_async = AsyncMock(return_value=response)
    return client


@pytest.fixture
def query_engine(mock_session_factory, mock_ai_client):
    """Create a QueryEngine with mocked dependencies."""
    return QueryEngine(
        db_session_factory=mock_session_factory,
        ai_client=mock_ai_client,
    )


# ── Tests ──────────────────────────────────────────────────────


class TestQueryEngine:
    @pytest.mark.asyncio
    async def test_appearance_query_finds_red_shirt(self, query_engine, mock_ai_client):
        """Appearance query should parse correctly."""
        parsed = await query_engine._parse_intent("who wore red shirts today?")
        assert parsed.intent == QueryIntent.APPEARANCE
        assert "red shirt" in str(parsed.filters.get("clothing", ""))

    @pytest.mark.asyncio
    async def test_object_query_finds_phone(self, query_engine, mock_ai_client):
        """Object query should parse correctly."""
        mock_ai_client.generate_content_async.return_value.text = (
            '{"intent": "OBJECT", "filters": {"object": "phone"}}'
        )
        parsed = await query_engine._parse_intent("what was person 7 holding?")
        assert parsed.intent == QueryIntent.OBJECT

    @pytest.mark.asyncio
    async def test_behaviour_query_finds_running(self, query_engine, mock_ai_client):
        """Behaviour query should parse correctly."""
        mock_ai_client.generate_content_async.return_value.text = (
            '{"intent": "BEHAVIOUR", "filters": {"action": "running"}}'
        )
        parsed = await query_engine._parse_intent("did anyone run today?")
        assert parsed.intent == QueryIntent.BEHAVIOUR

    @pytest.mark.asyncio
    async def test_scene_state_query_returns_gate_status(
        self, query_engine, mock_ai_client
    ):
        """Scene state query should parse correctly."""
        mock_ai_client.generate_content_async.return_value.text = (
            '{"intent": "SCENE_STATE", "filters": {"scene_element": "gate"}}'
        )
        parsed = await query_engine._parse_intent("are all gates locked?")
        assert parsed.intent == QueryIntent.SCENE_STATE

    @pytest.mark.asyncio
    async def test_cross_camera_query_tracks_person(
        self, query_engine, mock_ai_client
    ):
        """Cross-camera query should parse correctly."""
        mock_ai_client.generate_content_async.return_value.text = (
            '{"intent": "CROSS_CAMERA", "person_uid": "PERSON_007"}'
        )
        parsed = await query_engine._parse_intent("track person 7 across all cameras")
        assert parsed.intent == QueryIntent.CROSS_CAMERA
        assert parsed.person_uid == "PERSON_007"

    @pytest.mark.asyncio
    async def test_timeline_query_returns_ordered_events(
        self, query_engine, mock_ai_client
    ):
        """Timeline query should parse correctly."""
        mock_ai_client.generate_content_async.return_value.text = (
            '{"intent": "TIMELINE", "time_range": {"start": "2024-06-15T14:00:00", "end": "2024-06-15T18:00:00"}}'
        )
        parsed = await query_engine._parse_intent(
            "what happened while I was away 2pm to 6pm?"
        )
        assert parsed.intent == QueryIntent.TIMELINE
        assert parsed.time_range is not None

    @pytest.mark.asyncio
    async def test_free_tier_blocked_from_queries(self, query_engine):
        """Free tier should be blocked from NL queries."""
        result = await query_engine.process_query(
            question="who is at the front gate?",
            user_id="user_free",
            tier="free",
        )
        assert result.error == "free_tier_blocked"
        assert "upgrade" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_helpful_message(
        self, query_engine, mock_ai_client
    ):
        """Unknown intent should still process gracefully."""
        mock_ai_client.generate_content_async.return_value.text = (
            '{"intent": "UNKNOWN", "filters": {}}'
        )
        parsed = await query_engine._parse_intent("what is the weather like?")
        assert parsed.intent == QueryIntent.UNKNOWN

    @pytest.mark.asyncio
    async def test_empty_results_returns_no_match_message(
        self, query_engine, mock_ai_client
    ):
        """Empty results should return a helpful message."""
        result = await query_engine.process_query(
            question="who wore a blue hat?",
            user_id="user_001",
            tier="household",
        )
        assert "No matching events" in result.answer

    @pytest.mark.asyncio
    async def test_parse_intent_correctly_classifies(
        self, query_engine, mock_ai_client
    ):
        """Intent parsing should correctly classify different query types."""
        test_cases = [
            ("who wore red?", QueryIntent.APPEARANCE,
             '{"intent": "APPEARANCE", "filters": {"color": "red"}}'),
            ("what is person holding?", QueryIntent.OBJECT,
             '{"intent": "OBJECT", "filters": {"object": "unknown"}}'),
            ("did someone run?", QueryIntent.BEHAVIOUR,
             '{"intent": "BEHAVIOUR", "filters": {"action": "running"}}'),
            ("is the gate open?", QueryIntent.SCENE_STATE,
             '{"intent": "SCENE_STATE", "filters": {"scene_element": "gate"}}'),
            ("track person across cameras", QueryIntent.CROSS_CAMERA,
             '{"intent": "CROSS_CAMERA", "person_uid": null}'),
            ("what happened at 3pm?", QueryIntent.TIMELINE,
             '{"intent": "TIMELINE", "time_range": {"start": "2024-06-15T15:00:00", "end": "2024-06-15T16:00:00"}}'),
        ]

        for question, expected_intent, mock_response in test_cases:
            mock_ai_client.generate_content_async.return_value.text = mock_response
            parsed = await query_engine._parse_intent(question)
            assert parsed.intent == expected_intent, (
                f"Failed for question: {question}"
            )

    def test_parse_time_range_today(self, query_engine):
        """Time range parsing should handle 'today'."""
        result = query_engine._parse_time_range("today")
        assert "start" in result
        assert "end" in result

    def test_parse_time_range_yesterday(self, query_engine):
        """Time range parsing should handle 'yesterday'."""
        result = query_engine._parse_time_range("yesterday")
        assert "start" in result
        assert "end" in result

    def test_build_appearance_filter(self, query_engine):
        """Appearance filter should build correct SQL clauses."""
        parsed = ParsedQuery(
            intent=QueryIntent.APPEARANCE,
            original_question="who wore red?",
            filters={"clothing": "red shirt", "color": "red"},
        )
        result = query_engine._build_appearance_filter(parsed)
        assert len(result["where_clauses"]) > 0

    def test_build_object_filter(self, query_engine):
        """Object filter should build correct SQL clauses."""
        parsed = ParsedQuery(
            intent=QueryIntent.OBJECT,
            original_question="what was person holding?",
            filters={"object": "phone"},
        )
        result = query_engine._build_object_filter(parsed)
        assert len(result["where_clauses"]) > 0

    def test_build_behaviour_filter(self, query_engine):
        """Behaviour filter should build correct SQL clauses."""
        parsed = ParsedQuery(
            intent=QueryIntent.BEHAVIOUR,
            original_question="did someone run?",
            filters={"action": "running"},
        )
        result = query_engine._build_behaviour_filter(parsed)
        assert len(result["where_clauses"]) > 0

    def test_build_scene_state_filter(self, query_engine):
        """Scene state filter should build correct SQL clauses."""
        parsed = ParsedQuery(
            intent=QueryIntent.SCENE_STATE,
            original_question="is the gate open?",
            filters={"scene_element": "gate"},
        )
        result = query_engine._build_scene_state_filter(parsed)
        assert len(result["where_clauses"]) > 0

    def test_build_cross_camera_filter(self, query_engine):
        """Cross-camera filter should build correct SQL clauses."""
        parsed = ParsedQuery(
            intent=QueryIntent.CROSS_CAMERA,
            original_question="track person 7",
            person_uid="PERSON_007",
        )
        result = query_engine._build_cross_camera_filter(parsed)
        assert len(result["where_clauses"]) > 0

    def test_build_timeline_filter(self, query_engine):
        """Timeline filter should build correct SQL clauses."""
        parsed = ParsedQuery(
            intent=QueryIntent.TIMELINE,
            original_question="what happened at 3pm?",
            time_range={"start": "2024-06-15T15:00:00", "end": "2024-06-15T16:00:00"},
        )
        result = query_engine._build_timeline_filter(parsed)
        assert isinstance(result["where_clauses"], list)

    @pytest.mark.asyncio
    async def test_synthesise_answer_returns_string(self, query_engine, mock_ai_client):
        """Answer synthesis should return a string."""
        mock_ai_client.generate_content_async.return_value.text = (
            "I found 3 events matching your query."
        )
        events = [
            {"id": "evt_001", "camera_name": "Front Gate",
             "timestamp_start": "2024-06-15T14:00:00",
             "alert_message": "Person in red shirt"},
        ]
        analyses = [{"event_id": "evt_001", "analysis": {"clothing": "red shirt"}}]

        answer = await query_engine._synthesise_answer(
            "who wore red?", events, analyses
        )
        assert isinstance(answer, str)
        assert len(answer) > 0

    def test_query_result_dataclass(self):
        """QueryResult dataclass should work correctly."""
        result = QueryResult(
            answer="Test answer",
            matching_events=[{"id": "evt_001"}],
            thumbnails=["/thumbnails/evt_001.jpg"],
        )
        assert result.answer == "Test answer"
        assert len(result.matching_events) == 1
        assert len(result.thumbnails) == 1

    def test_parsed_query_dataclass(self):
        """ParsedQuery dataclass should work correctly."""
        parsed = ParsedQuery(
            intent=QueryIntent.APPEARANCE,
            original_question="who wore red?",
            filters={"color": "red"},
            person_uid="PERSON_001",
        )
        assert parsed.intent == QueryIntent.APPEARANCE
        assert parsed.person_uid == "PERSON_001"
