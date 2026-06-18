"""
query_engine.py — Natural Language Query Engine for Vision OS.

Users type questions in natural language about their security events.
Flow: NL -> intent parsing -> SQL filter -> fetch events -> Gemini synthesis -> answer

Query types:
- APPEARANCE: "who wore red shirts today?"
- OBJECT: "what was person 7 holding?"
- SCENE_STATE: "are all gates locked?"
- BEHAVIOUR: "did anyone run today?"
- CROSS_CAMERA: "track person 7 across all cameras"
- TIMELINE: "what happened while I was away 2pm to 6pm?"
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    APPEARANCE = "appearance"
    OBJECT = "object"
    SCENE_STATE = "scene_state"
    BEHAVIOUR = "behaviour"
    CROSS_CAMERA = "cross_camera"
    TIMELINE = "timeline"
    UNKNOWN = "unknown"


@dataclass
class ParsedQuery:
    intent: QueryIntent
    original_question: str
    filters: dict = field(default_factory=dict)
    person_uid: Optional[str] = None
    time_range: Optional[dict] = None
    cameras: Optional[list[str]] = None


@dataclass
class QueryResult:
    answer: str
    matching_events: list[dict] = field(default_factory=list)
    thumbnails: list[str] = field(default_factory=list)
    error: Optional[str] = None


# ── Intent Classification Prompts ──────────────────────────────

INTENT_PROMPT = """You are a security query classifier for Vision OS CCTV system.
Classify the user's question into one of these intents:

APPEARANCE: Questions about what people look like (clothing, colors, accessories)
OBJECT: Questions about objects people are holding or carrying
SCENE_STATE: Questions about the state of the scene (gates, doors, vehicles)
BEHAVIOUR: Questions about actions or behaviour (running, climbing, fighting)
CROSS_CAMERA: Questions about tracking a person across multiple cameras
TIMELINE: Questions about what happened during a specific time period
UNKNOWN: Questions that don't fit any category

Respond with JSON only:
{"intent": "APPEARANCE|OBJECT|SCENE_STATE|BEHAVIOUR|CROSS_CAMERA|TIMELINE|UNKNOWN",
 "person_uid": null or "PERSON_XXX",
 "time_range": null or {"start": "ISO datetime", "end": "ISO datetime"},
 "cameras": null or ["cam_001", "cam_002"],
 "filters": {"clothing": null, "color": null, "object": null, "action": null, "scene_element": null}}

Question: {question}"""

SYNTHESIS_PROMPT = """You are a security analyst for Vision OS CCTV system.
Based on the following security events and their AI analysis, answer the user's question.

Question: {question}

Matching Events:
{events}

Provide a clear, concise answer in plain text. Include person IDs and timestamps where relevant.
If no matching events were found, say so clearly.
Answer:"""


class QueryEngine:
    """Natural language query engine for security events."""

    def __init__(self, db_session_factory, ai_client):
        """Initialize query engine.

        Args:
            db_session_factory: SQLAlchemy async session factory.
            ai_client: AI client for Gemini intent parsing + answer synthesis.
        """
        self.db_session_factory = db_session_factory
        self.ai_client = ai_client

    async def process_query(self, question: str, user_id: str,
                            tier: str,
                            cameras: Optional[list[str]] = None,
                            time_range: Optional[str] = None) -> QueryResult:
        """Process a natural language query end-to-end.

        Steps:
        1. Parse intent with Gemini
        2. Build SQL filters from parsed intent
        3. Fetch matching events from database
        4. Retrieve stored vision analysis JSON for matches
        5. If not stored, re-analyse thumbnail via Gemini
        6. Synthesise final answer with Gemini
        7. Return QueryResult with answer + thumbnails

        Args:
            question: Natural language question.
            user_id: User UUID.
            tier: User tier (free/household/business).
            cameras: Optional list of camera IDs to scope the query.
            time_range: Optional time range string ("today", "2pm to 6pm", etc).

        Returns:
            QueryResult with answer and matching events.

        Raises:
            ValueError: If tier is "free" (NL queries require household+).
        """
        if tier == "free":
            return QueryResult(
                answer="Natural language queries are available on Household and Business tiers. "
                       "Please upgrade to use this feature.",
                error="free_tier_blocked",
            )

        # Step 1: Parse intent
        parsed = await self._parse_intent(question)

        # Apply optional scoping
        if cameras:
            parsed.cameras = cameras
        if time_range:
            parsed.time_range = self._parse_time_range(time_range)

        # Step 2: Build SQL filters
        sql_filter = await self._build_sql_filter(parsed, user_id)

        # Step 3: Fetch matching events
        events = await self._fetch_matching_events(sql_filter)

        if not events:
            return QueryResult(
                answer="No matching events found for your question. "
                       "Try rephrasing or checking a different time period.",
                matching_events=[],
            )

        # Step 4 & 5: Get vision analyses
        analyses = await self._get_vision_analyses(events)

        # Step 6: Synthesise answer
        answer = await self._synthesise_answer(question, events, analyses)

        # Extract thumbnails
        thumbnails = [e.get("thumbnail_url") for e in events if e.get("thumbnail_url")]

        return QueryResult(
            answer=answer,
            matching_events=events,
            thumbnails=thumbnails,
        )

    async def _parse_intent(self, question: str) -> ParsedQuery:
        """Parse user question to extract intent + filters.

        Uses Gemini 2.0 Flash to classify and extract parameters.

        Args:
            question: Natural language question.

        Returns:
            ParsedQuery with intent and filter params.
        """
        prompt = INTENT_PROMPT.replace("{question}", question)

        try:
            response = await self.ai_client.generate_content_async(prompt)
            text = response.text.strip()

            # Extract JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            intent_str = data.get("intent", "UNKNOWN").upper()
            try:
                intent = QueryIntent(intent_str.lower())
            except ValueError:
                intent = QueryIntent.UNKNOWN

            return ParsedQuery(
                intent=intent,
                original_question=question,
                filters=data.get("filters", {}),
                person_uid=data.get("person_uid"),
                time_range=data.get("time_range"),
                cameras=data.get("cameras"),
            )
        except Exception as exc:
            logger.error("Intent parsing failed: %s", exc, exc_info=True)
            return ParsedQuery(
                intent=QueryIntent.UNKNOWN,
                original_question=question,
            )

    async def _build_sql_filter(self, parsed: ParsedQuery,
                                user_id: str) -> dict:
        """Build SQL filter dict from parsed query.

        Maps intent to appropriate table columns and conditions.

        Args:
            parsed: ParsedQuery with intent and filters.
            user_id: User UUID.

        Returns:
            Dict with where_clauses, joins, order, limit.
        """
        base_filter = {
            "where_clauses": [f"user_id = '{user_id}'"],
            "joins": [],
            "order": "timestamp_start DESC",
            "limit": 20,
        }

        # Add time range filter
        if parsed.time_range:
            start = parsed.time_range.get("start")
            end = parsed.time_range.get("end")
            if start:
                base_filter["where_clauses"].append(
                    f"timestamp_start >= '{start}'"
                )
            if end:
                base_filter["where_clauses"].append(
                    f"timestamp_start <= '{end}'"
                )
        else:
            # Default to today
            today = date.today().isoformat()
            base_filter["where_clauses"].append(
                f"timestamp_start >= '{today}'"
            )

        # Add camera filter
        if parsed.cameras:
            cam_list = ", ".join(f"'{c}'" for c in parsed.cameras)
            base_filter["where_clauses"].append(
                f"camera_id IN ({cam_list})"
            )

        # Add person filter
        if parsed.person_uid:
            base_filter["where_clauses"].append(
                f"person_ids @> ARRAY['{parsed.person_uid}']"
            )

        # Intent-specific filters
        intent_builders = {
            QueryIntent.APPEARANCE: self._build_appearance_filter,
            QueryIntent.OBJECT: self._build_object_filter,
            QueryIntent.BEHAVIOUR: self._build_behaviour_filter,
            QueryIntent.SCENE_STATE: self._build_scene_state_filter,
            QueryIntent.CROSS_CAMERA: self._build_cross_camera_filter,
            QueryIntent.TIMELINE: self._build_timeline_filter,
        }

        builder = intent_builders.get(parsed.intent)
        if builder:
            extra = builder(parsed)
            if extra:
                base_filter["where_clauses"].extend(
                    extra.get("where_clauses", [])
                )
                base_filter["joins"].extend(extra.get("joins", []))

        return base_filter

    async def _fetch_matching_events(self, sql_filter: dict) -> list[dict]:
        """Fetch matching events from database using SQL filter.

        Args:
            sql_filter: Dict with where_clauses, joins, order, limit.

        Returns:
            List of event dicts with id, timestamp, camera_id, thumbnail_url.
        """
        # In production, this would execute a real SQL query
        # For now, return mock data for development
        logger.info("Fetching events with filter: %s", sql_filter)
        return []

    async def _get_vision_analyses(self, events: list[dict]) -> list[dict]:
        """Get stored vision analysis JSON for matching events.

        If not stored, re-analyse thumbnail via Gemini.

        Args:
            events: List of event dicts.

        Returns:
            List of analysis dicts.
        """
        analyses = []
        for event in events:
            # In production, fetch from database
            # If not found, re-analyse thumbnail
            analyses.append({
                "event_id": event.get("id"),
                "analysis": event.get("vision_analysis", {}),
            })
        return analyses

    async def _synthesise_answer(self, question: str,
                                  events: list[dict],
                                  analyses: list[dict]) -> str:
        """Synthesise final answer using Gemini 2.0 Flash.

        Args:
            question: Original user question.
            events: List of matching event dicts.
            analyses: List of vision analysis dicts.

        Returns:
            Plain text answer with person IDs and timestamps.
        """
        # Format events for the prompt
        event_lines = []
        for i, (event, analysis) in enumerate(zip(events, analyses)):
            line = (
                f"Event {i + 1}: {event.get('camera_name', 'Unknown')} "
                f"at {event.get('timestamp_start', 'Unknown')} - "
                f"{event.get('alert_message', 'No description')}"
            )
            if analysis.get("analysis"):
                line += f" | Analysis: {analysis['analysis']}"
            event_lines.append(line)

        events_text = "\n".join(event_lines) if event_lines else "No events found."

        prompt = SYNTHESIS_PROMPT.format(
            question=question,
            events=events_text,
        )

        try:
            response = await self.ai_client.generate_content_async(prompt)
            return response.text.strip()
        except Exception as exc:
            logger.error("Answer synthesis failed: %s", exc, exc_info=True)
            return "Unable to generate answer due to a processing error."

    def _parse_time_range(self, time_range: str) -> dict:
        """Parse a time range string into start/end datetimes.

        Args:
            time_range: String like "today", "2pm to 6pm", "yesterday".

        Returns:
            Dict with start and end ISO datetime strings.
        """
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if time_range.lower() == "today":
            return {
                "start": today.isoformat(),
                "end": now.isoformat(),
            }
        elif time_range.lower() == "yesterday":
            yesterday = today - timedelta(days=1)
            return {
                "start": yesterday.isoformat(),
                "end": today.isoformat(),
            }
        else:
            # Default to today
            return {
                "start": today.isoformat(),
                "end": now.isoformat(),
            }

    def _get_query_prompt(self, parsed: ParsedQuery) -> str:
        """Get the appropriate Gemini prompt template for the query intent.

        Args:
            parsed: ParsedQuery with intent.

        Returns:
            Prompt template string.
        """
        prompts = {
            QueryIntent.APPEARANCE: (
                "Find events where a person matching this description was seen: "
                "clothing={clothing}, color={color}. "
                "Return person IDs and camera locations."
            ),
            QueryIntent.OBJECT: (
                "Find events where a person was seen holding or carrying: {object}. "
                "Return person IDs and timestamps."
            ),
            QueryIntent.BEHAVIOUR: (
                "Find events where a person was observed: {action}. "
                "Return person IDs, camera locations, and timestamps."
            ),
            QueryIntent.SCENE_STATE: (
                "Check the state of: {scene_element}. "
                "Return current status and any recent changes."
            ),
            QueryIntent.CROSS_CAMERA: (
                "Track person {person_uid} across all cameras. "
                "Return timeline of sightings with camera names and timestamps."
            ),
            QueryIntent.TIMELINE: (
                "Return a chronological timeline of all events "
                "between {time_range[start]} and {time_range[end]}. "
                "Group by camera and sort by time."
            ),
        }
        return prompts.get(parsed.intent, "Describe what happened.")

    def _build_appearance_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for appearance queries (clothing, colors, accessories).

        Args:
            parsed: ParsedQuery with appearance filters.

        Returns:
            Dict with where_clauses.
        """
        clauses = []
        filters = parsed.filters or {}

        clothing = filters.get("clothing")
        if clothing:
            clauses.append(f"vision_analysis->>'clothing' ILIKE '%{clothing}%'")

        color = filters.get("color")
        if color:
            clauses.append(f"vision_analysis->>'clothing' ILIKE '%{color}%'")

        return {"where_clauses": clauses, "joins": []}

    def _build_object_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for object-in-hand queries.

        Args:
            parsed: ParsedQuery with object filters.

        Returns:
            Dict with where_clauses.
        """
        clauses = []
        filters = parsed.filters or {}

        obj = filters.get("object")
        if obj:
            clauses.append(f"vision_analysis->>'hand_objects' ILIKE '%{obj}%'")

        return {"where_clauses": clauses, "joins": []}

    def _build_behaviour_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for behaviour queries (running, climbing, etc).

        Args:
            parsed: ParsedQuery with behaviour filters.

        Returns:
            Dict with where_clauses.
        """
        clauses = []
        filters = parsed.filters or {}

        action = filters.get("action")
        if action:
            clauses.append(f"vision_analysis->>'action' ILIKE '%{action}%'")

        return {"where_clauses": clauses, "joins": []}

    def _build_scene_state_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for scene state queries (gates, doors, vehicles).

        Args:
            parsed: ParsedQuery with scene state filters.

        Returns:
            Dict with where_clauses.
        """
        clauses = []
        filters = parsed.filters or {}

        scene_element = filters.get("scene_element")
        if scene_element:
            clauses.append(
                f"(vision_analysis->>'scene' ILIKE '%{scene_element}%' "
                f"OR alert_message ILIKE '%{scene_element}%')"
            )

        return {"where_clauses": clauses, "joins": []}

    def _build_cross_camera_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for cross-camera person tracking queries.

        Args:
            parsed: ParsedQuery with person_uid.

        Returns:
            Dict with where_clauses.
        """
        clauses = []
        if parsed.person_uid:
            clauses.append(f"person_ids @> ARRAY['{parsed.person_uid}']")

        return {"where_clauses": clauses, "joins": []}

    def _build_timeline_filter(self, parsed: ParsedQuery) -> dict:
        """Build SQL filter for timeline queries (time range).

        Args:
            parsed: ParsedQuery with time_range.

        Returns:
            Dict with where_clauses.
        """
        # Time range is already handled in _build_sql_filter
        return {"where_clauses": [], "joins": []}
