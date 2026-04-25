"""
queries.py — Natural Language Query API stubs for Vision OS.

Allows Household and Business tier users to submit NL queries
about their camera footage.
All routes are protected with Firebase Auth.
Real logic will be added in Phase 3.
"""

from fastapi import APIRouter, Depends

from backend.dashboard.auth import get_current_user, require_tier

router = APIRouter(prefix="/queries", tags=["queries"])


@router.post("")
@require_tier("household")
async def submit_query(
    query_data: dict,
    user: dict = Depends(get_current_user),
):
    """Submit a natural language query (Household/Business only).

    Args:
        query_data: Dict with question, optional cameras list, optional time_range.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with answer, matching_events, thumbnails.

    Body:
        {
            "question": "Who wore a red shirt this morning?",
            "cameras": ["CAM_FRONT_001"],
            "time_range": "2026-04-25T06:00:00/2026-04-25T12:00:00"
        }

    TODO: Sprint 5.2 — call query_engine
    """
    question = query_data.get("question", "")
    cameras = query_data.get("cameras", None)
    time_range = query_data.get("time_range", None)

    return {
        "answer": f"Query received: '{question}'. Processing will be available in Phase 3.",
        "matching_events": [],
        "thumbnails": [],
        "query_details": {
            "question": question,
            "cameras": cameras,
            "time_range": time_range,
        },
    }
