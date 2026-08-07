"""
query_agent.py — Agentic natural-language query engine for Vision OS.

Replaces two things that predated this module:
  - backend/ai/query_engine.py: a fixed intent-classify -> hand-built-SQL
    pipeline that was never wired into the app (nothing imported it outside
    its own test) and whose DB-fetch step was a stub that always returned [].
  - backend/api/queries.py's live POST /queries/natural handler, which did a
    plain substring search over incident_id/camera_id with zero LLM calls.

Gemini gets function-calling access to a small set of read-only tools
instead of a fixed pipeline, so it can decide what to look up (and look up
more than once) before answering. Bounded to MAX_TOOL_CALLS real Gemini
calls per question, then forced to answer with whatever it has.

Data model reality check: persons / person_sightings / scene_states are not
populated by the live pipeline today (nothing calls create_sighting() or
upsert_person(), and Person.embedding is a random vector when boxmot isn't
installed — see CLAUDE.md). Tools are scoped to what `events` actually
holds: threat_level, camera_id, timestamps, alert_message, and person_ids
(stored inside gemini_decision). A find_similar_persons/get_scene_state
tool would just be extra surface area with no real data behind it.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    Part,
    GenerativeModel,
    Tool,
)

from backend.ai.ai_client import _init_vertex, _rate_limit, _make_gen_config

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 4
MAX_OUTPUT_TOKENS = 2048
SEARCH_EVENTS_MAX_LIMIT = 50

SYSTEM_INSTRUCTION = (
    "You are a security analyst assistant for Vision OS, a CCTV intelligence "
    "system. Answer the user's question about their security camera events "
    "using the provided tools to look up real data — never invent event IDs, "
    "person IDs, timestamps, or counts. If a tool returns no matching data, "
    "say so plainly instead of guessing. Keep answers concise and reference "
    "specific event IDs, camera names, and timestamps when relevant."
)

_SEARCH_EVENTS = FunctionDeclaration(
    name="search_events",
    description=(
        "Search the user's security events by time range, camera, and/or "
        "threat level. Returns event summaries (event_id, camera, "
        "timestamp, threat level, alert message, person_ids)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "start_time": {
                "type": "string",
                "description": "ISO 8601 datetime, inclusive lower bound on "
                               "event start time. Omit for no lower bound.",
            },
            "end_time": {
                "type": "string",
                "description": "ISO 8601 datetime, inclusive upper bound on "
                               "event start time. Omit for no upper bound.",
            },
            "camera_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Restrict to these camera IDs. Omit to "
                               "search all of the user's cameras.",
            },
            "threat_level": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL", "EMERGENCY"],
                "description": "Restrict to events at exactly this threat level.",
            },
            "limit": {
                "type": "integer",
                "description": "Max events to return (default 20, max 50).",
            },
        },
    },
)

_GET_EVENT_DETAIL = FunctionDeclaration(
    name="get_event_detail",
    description=(
        "Get full detail for one event by its event_id, including the "
        "alert message and involved person IDs. Use this after "
        "search_events to dig into a specific event."
    ),
    parameters={
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "The event_id returned by search_events.",
            },
        },
        "required": ["event_id"],
    },
)

_GET_PERSON_SIGHTINGS = FunctionDeclaration(
    name="get_person_sightings",
    description=(
        "Find every event a given person_uid (e.g. 'PERSON_007') appears "
        "in, across all cameras, to trace where and when that person was "
        "seen. Get the person_uid from a prior search_events/get_event_detail "
        "call's person_ids field."
    ),
    parameters={
        "type": "object",
        "properties": {
            "person_uid": {
                "type": "string",
                "description": "Person identifier, e.g. PERSON_007.",
            },
        },
        "required": ["person_uid"],
    },
)

_TOOLS = Tool(function_declarations=[
    _SEARCH_EVENTS, _GET_EVENT_DETAIL, _GET_PERSON_SIGHTINGS,
])

_tool_model = None


def _get_tool_model() -> GenerativeModel:
    """Lazy-init a Gemini model instance with the query tools attached.

    Deliberately separate from ai_client._get_model()'s singleton — that
    one has no tools attached and is used for the per-frame vision/decision
    prompts, which must not pay for tool-declaration tokens on every call.
    """
    global _tool_model
    if _tool_model is None:
        _init_vertex()
        _tool_model = GenerativeModel(
            "gemini-2.5-flash",
            tools=[_TOOLS],
            system_instruction=SYSTEM_INSTRUCTION,
        )
    return _tool_model


@dataclass
class QueryAgentResult:
    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    error: Optional[str] = None


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string from Gemini into a UTC-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        logger.warning("query_agent: could not parse datetime %r", value)
        return None


def _event_summary(e) -> dict:
    return {
        "event_id": e.event_id,
        "camera_id": e.camera_id,
        "threat_level": e.threat_level,
        "timestamp_start": e.timestamp_start,
        "alert_message": e.alert_message,
        "person_ids": e.person_ids,
    }


def _event_detail(e) -> dict:
    return {
        "event_id": e.event_id,
        "camera_id": e.camera_id,
        "threat_level": e.threat_level,
        "timestamp_start": e.timestamp_start,
        "timestamp_end": e.timestamp_end,
        "duration_sec": e.duration_sec,
        "alert_message": e.alert_message,
        "person_ids": e.person_ids,
    }


async def _execute_tool(name: str, args: dict, user_id: str, crud) -> dict:
    """Dispatch a Gemini function call to the real CRUD layer.

    Every branch is wrapped so a single bad tool call (malformed args,
    transient DB error) returns an {"error": ...} dict to Gemini instead of
    blowing up the whole query — Gemini can then explain the failure or try
    a different tool/argument instead of the request 500ing.
    """
    try:
        if name == "search_events":
            limit = min(int(args.get("limit") or 20), SEARCH_EVENTS_MAX_LIMIT)
            events = await crud.search_events(
                user_id,
                start_time=_parse_iso(args.get("start_time")),
                end_time=_parse_iso(args.get("end_time")),
                camera_ids=args.get("camera_ids") or None,
                threat_level=args.get("threat_level") or None,
                limit=limit,
            )
            return {"events": [_event_summary(e) for e in events], "count": len(events)}

        if name == "get_event_detail":
            event = await crud.get_event_by_id(args.get("event_id", ""), user_id)
            if event is None:
                return {"error": f"No event found with id {args.get('event_id')!r}"}
            return _event_detail(event)

        if name == "get_person_sightings":
            person_uid = args.get("person_uid", "")
            events = await crud.get_events_by_person(user_id, person_uid)
            return {
                "person_uid": person_uid,
                "sightings": [_event_summary(e) for e in events],
                "count": len(events),
            }

        return {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.error("Query agent tool %s failed: %s", name, exc, exc_info=True)
        return {"error": f"Tool execution failed: {exc}"}


async def answer_question(question: str, user_id: str, tier: str, crud) -> QueryAgentResult:
    """Answer a natural language question about security events, agentically.

    Args:
        question: The user's plain-language question.
        user_id: Authenticated user's UUID — every tool call is scoped to
                 this user, Gemini never sees or chooses the user_id.
        tier: User's subscription tier — NL queries require household+.
        crud: HybridCRUD instance (or anything exposing the same
              search_events/get_event_by_id/get_events_by_person methods).

    Returns:
        QueryAgentResult with the final answer and a trace of tool calls
        made (useful for debugging/tuning, not shown to the end user).
    """
    if tier == "free":
        return QueryAgentResult(
            answer="Natural language queries are available on Household and "
                   "Business tiers. Please upgrade to use this feature.",
            error="free_tier_blocked",
        )

    model = _get_tool_model()
    history = [Content(role="user", parts=[Part.from_text(question)])]
    tool_calls: list[dict] = []
    gen_config = _make_gen_config(max_tokens=MAX_OUTPUT_TOKENS)

    try:
        for _ in range(MAX_TOOL_CALLS):
            if not await _rate_limit():
                return QueryAgentResult(
                    answer="The system is busy processing camera events right "
                           "now — please try your question again in a few seconds.",
                    tool_calls=tool_calls,
                    error="rate_limited",
                )

            response = await model.generate_content_async(
                history, generation_config=gen_config,
            )
            candidate = response.candidates[0]
            part = candidate.content.parts[0]
            fc = part.function_call

            if fc and fc.name:
                args = dict(fc.args) if fc.args else {}
                result = await _execute_tool(fc.name, args, user_id, crud)
                tool_calls.append({"name": fc.name, "args": args, "result": result})
                history.append(candidate.content)
                history.append(Content(
                    role="function",
                    parts=[Part.from_function_response(name=fc.name, response=result)],
                ))
                continue

            return QueryAgentResult(answer=(part.text or "").strip(), tool_calls=tool_calls)

        # Exhausted MAX_TOOL_CALLS without a text answer — force one, with
        # no tools attached, using whatever context has been gathered.
        history.append(Content(
            role="user",
            parts=[Part.from_text(
                "Based on everything you've found so far, answer the "
                "original question now. Do not call any more tools."
            )],
        ))
        if not await _rate_limit():
            return QueryAgentResult(
                answer="Unable to complete the query — the system is busy. "
                       "Please try again shortly.",
                tool_calls=tool_calls,
                error="rate_limited",
            )
        response = await model.generate_content_async(
            history, tools=[], generation_config=gen_config,
        )
        final_text = (response.candidates[0].content.parts[0].text or "").strip()
        return QueryAgentResult(
            answer=final_text or "Unable to determine an answer from the available data.",
            tool_calls=tool_calls,
        )

    except Exception as exc:
        logger.error("Query agent failed: %s", exc, exc_info=True)
        return QueryAgentResult(
            answer="Unable to answer your question due to a processing error.",
            tool_calls=tool_calls,
            error=str(exc),
        )
