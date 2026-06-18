"""
queries.py — Natural Language Query API for Vision OS (Hybrid Backend).

Provides natural language querying of security events and query history.
Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from backend.dashboard.auth import get_current_user
from backend.storage.hybrid_crud import HybridCRUD

router = APIRouter(prefix="/queries", tags=["queries"])

# Global HybridCRUD instance (initialized in server.py)
hybrid_crud: HybridCRUD = None  # type: ignore


def get_crud() -> HybridCRUD:
    """Dependency to get the HybridCRUD instance.

    Returns:
        HybridCRUD instance.

    Raises:
        HTTPException 503: If no storage backend is available.
    """
    if hybrid_crud is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "Storage not initialized", "code": "STORAGE_UNAVAILABLE"},
        )
    return hybrid_crud


# In-memory query history (could be stored in DB for persistence)
_query_history: list[dict] = []


@router.post("/natural")
async def natural_language_query(
    query_data: dict,
    user: dict = Depends(get_current_user),
    crud: HybridCRUD = Depends(get_crud),
):
    """Process a natural language query about security events.

    Parses the query text and searches events by type, camera, or details.
    Returns matching events with confidence scores.

    Args:
        query_data: Dict with query string and optional camera_id.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with answer, events_found, and confidence.

    Raises:
        HTTPException 422: If query is missing.
    """
    user_id = user.get("uid", "anonymous")
    query = query_data.get("query", "").strip()
    camera_id = query_data.get("camera_id")

    if not query:
        raise HTTPException(status_code=422, detail={
            "error": "Query is required", "code": "VALIDATION_ERROR",
        })

    try:
        # Search events matching the query
        events = await crud.search_events(user_id, query)

        # If camera_id specified, filter further
        if camera_id:
            events = [e for e in events if e.camera_id == camera_id]

        # Build a natural language answer
        if not events:
            answer = f"No events found matching '{query}'."
        else:
            event_types = set(e.event_type for e in events)
            answer = (
                f"Found {len(events)} event(s) matching '{query}'. "
                f"Types detected: {', '.join(event_types)}. "
                f"Most recent: {events[0].event_type} at {events[0].created_at}."
            )

        # Record query in history
        _query_history.append({
            "query": query,
            "user_id": user_id,
            "camera_id": camera_id,
            "results_count": len(events),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep history manageable
        if len(_query_history) > 100:
            _query_history[:] = _query_history[-100:]

        return {
            "answer": answer,
            "events_found": len(events),
            "confidence": max((e.confidence for e in events), default=0.0),
            "events": [{
                "event_id": e.event_id,
                "camera_id": e.camera_id,
                "event_type": e.event_type,
                "confidence": e.confidence,
                "created_at": e.created_at,
            } for e in events[:10]],  # Return top 10
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={
            "error": str(e), "code": "STORAGE_ERROR",
        })


@router.get("/history")
async def get_query_history(
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get the authenticated user's query history.

    Args:
        limit: Maximum number of history entries to return.
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with history list.
    """
    user_id = user.get("uid", "anonymous")
    user_history = [
        h for h in _query_history
        if h.get("user_id") == user_id
    ]
    user_history.reverse()  # Most recent first
    return {
        "history": user_history[:limit],
        "total": len(user_history),
    }
