"""Tests for backend/ai/query_agent.py — the Gemini function-calling query agent.

Mocks the Vertex AI model entirely (no real network calls) and exercises:
- the free-tier gate
- each tool's dispatch against a fake CRUD
- the loop terminating on a text-only response
- the loop being forced to a final answer after MAX_TOOL_CALLS
- the rate-limit short-circuit
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.ai import query_agent
from backend.storage.hybrid_crud import Event


class FakeFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class FakePart:
    def __init__(self, function_call=None, text=None):
        self.function_call = function_call
        self.text = text


class FakeContent:
    def __init__(self, parts):
        self.parts = parts


class FakeCandidate:
    def __init__(self, content):
        self.content = content


class FakeResponse:
    def __init__(self, part):
        self.candidates = [FakeCandidate(FakeContent([part]))]


def text_response(text):
    return FakeResponse(FakePart(function_call=None, text=text))


def tool_call_response(name, args):
    return FakeResponse(FakePart(function_call=FakeFunctionCall(name, args), text=None))


class FakeCrud:
    """Stand-in for HybridCRUD that records calls and returns canned data."""

    def __init__(self, events=None):
        self.events = events or []
        self.calls = []

    async def search_events(self, user_id, start_time=None, end_time=None,
                             camera_ids=None, threat_level=None, limit=20):
        self.calls.append(("search_events", user_id, start_time, end_time, camera_ids, threat_level, limit))
        return self.events

    async def get_event_by_id(self, event_id, user_id):
        self.calls.append(("get_event_by_id", event_id, user_id))
        for e in self.events:
            if e.event_id == event_id:
                return e
        return None

    async def get_events_by_person(self, user_id, person_uid, limit=200):
        self.calls.append(("get_events_by_person", user_id, person_uid, limit))
        return [e for e in self.events if person_uid in (e.person_ids or [])]


def make_model(responses):
    model = AsyncMock()
    model.generate_content_async = AsyncMock(side_effect=responses)
    return model


@pytest.mark.asyncio
async def test_free_tier_blocked():
    crud = FakeCrud()
    result = await query_agent.answer_question("who was here today?", "user1", "free", crud)
    assert result.error == "free_tier_blocked"
    assert "upgrade" in result.answer.lower()
    assert crud.calls == []


@pytest.mark.asyncio
async def test_answers_directly_when_no_tool_call_needed():
    model = make_model([text_response("I don't have enough information to answer that.")])
    crud = FakeCrud()
    with patch.object(query_agent, "_get_tool_model", return_value=model), \
         patch.object(query_agent, "_rate_limit", AsyncMock(return_value=True)):
        result = await query_agent.answer_question("hello?", "user1", "household", crud)
    assert result.answer == "I don't have enough information to answer that."
    assert result.tool_calls == []
    model.generate_content_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_events_tool_round_trip():
    event = Event(
        event_id="EVT_1", user_id="user1", camera_id="CAM_1",
        threat_level="HIGH", alert_message="Person loitering", person_ids=["PERSON_007"],
    )
    crud = FakeCrud(events=[event])
    model = make_model([
        tool_call_response("search_events", {"threat_level": "HIGH", "limit": 5}),
        text_response("There was one HIGH threat event: EVT_1 (person loitering)."),
    ])
    with patch.object(query_agent, "_get_tool_model", return_value=model), \
         patch.object(query_agent, "_rate_limit", AsyncMock(return_value=True)):
        result = await query_agent.answer_question(
            "any high threat events today?", "user1", "business", crud,
        )

    assert "EVT_1" in result.answer
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "search_events"
    assert result.tool_calls[0]["result"]["count"] == 1
    call = crud.calls[0]
    assert call[0] == "search_events"
    assert call[1] == "user1"  # user_id always comes from the caller, never from Gemini args
    assert call[5] == "HIGH"   # threat_level
    assert call[6] == 5        # limit


@pytest.mark.asyncio
async def test_get_person_sightings_tool():
    event = Event(event_id="EVT_2", user_id="user1", camera_id="CAM_2", person_ids=["PERSON_007"])
    crud = FakeCrud(events=[event])
    model = make_model([
        tool_call_response("get_person_sightings", {"person_uid": "PERSON_007"}),
        text_response("PERSON_007 was seen once, on CAM_2."),
    ])
    with patch.object(query_agent, "_get_tool_model", return_value=model), \
         patch.object(query_agent, "_rate_limit", AsyncMock(return_value=True)):
        result = await query_agent.answer_question(
            "where has PERSON_007 been seen?", "user1", "household", crud,
        )

    assert "PERSON_007" in result.answer
    assert crud.calls[0][:2] == ("get_events_by_person", "user1")


@pytest.mark.asyncio
async def test_unknown_event_id_returns_tool_error_not_a_crash():
    crud = FakeCrud(events=[])
    model = make_model([
        tool_call_response("get_event_detail", {"event_id": "EVT_MISSING"}),
        text_response("I couldn't find that event."),
    ])
    with patch.object(query_agent, "_get_tool_model", return_value=model), \
         patch.object(query_agent, "_rate_limit", AsyncMock(return_value=True)):
        result = await query_agent.answer_question(
            "what happened in EVT_MISSING?", "user1", "household", crud,
        )

    assert "error" in result.tool_calls[0]["result"]
    assert result.error is None  # a per-tool error is not a query-level error


@pytest.mark.asyncio
async def test_loop_forces_final_answer_after_max_tool_calls():
    # Keep calling the same tool forever — the loop must bail after
    # MAX_TOOL_CALLS and force a tools-free final answer instead of looping
    # (and paying for Gemini calls) indefinitely.
    responses = [
        tool_call_response("search_events", {"limit": 1})
        for _ in range(query_agent.MAX_TOOL_CALLS)
    ] + [text_response("Here is what I found across multiple searches.")]
    model = make_model(responses)
    crud = FakeCrud(events=[])
    with patch.object(query_agent, "_get_tool_model", return_value=model), \
         patch.object(query_agent, "_rate_limit", AsyncMock(return_value=True)):
        result = await query_agent.answer_question(
            "search everything", "user1", "business", crud,
        )

    assert result.answer == "Here is what I found across multiple searches."
    assert len(result.tool_calls) == query_agent.MAX_TOOL_CALLS
    # MAX_TOOL_CALLS tool-call responses + 1 forced final-answer call
    assert model.generate_content_async.await_count == query_agent.MAX_TOOL_CALLS + 1
    # The forced final call must not offer tools again
    final_call_kwargs = model.generate_content_async.await_args_list[-1].kwargs
    assert final_call_kwargs.get("tools") == []


@pytest.mark.asyncio
async def test_rate_limited_returns_gracefully():
    model = make_model([text_response("unused")])
    crud = FakeCrud()
    with patch.object(query_agent, "_get_tool_model", return_value=model), \
         patch.object(query_agent, "_rate_limit", AsyncMock(return_value=False)):
        result = await query_agent.answer_question(
            "any events?", "user1", "household", crud,
        )

    assert result.error == "rate_limited"
    model.generate_content_async.assert_not_awaited()
