"""
queries.py — Natural Language Query API for Vision OS (Hybrid Backend).

Provides natural language querying of security events and query history.
Uses HybridCRUD which falls back to PostgreSQL when MEGA.nz is unavailable.

The /natural endpoint delegates to backend.ai.query_agent — a Gemini
function-calling agent that looks up real event data via HybridCRUD,
rather than doing keyword matching itself.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from backend.ai.query_agent import answer_question
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
    """Answer a natural language question about security events.

    Runs the question through the Gemini-backed query agent
    (backend.ai.query_agent), which looks up real event data via tool
    calls before answering — see that module for the tool set and loop.

    Args:
        query_data: Dict with "query" (the question text).
        user: Authenticated user dict from Firebase.

    Returns:
        Dict with answer and a debug trace of tool calls made.

    Raises:
        HTTPException 422: If query is missing.
    """
    user_id = user.get("uid", "anonymous")
    tier = user.get("tier", "free")
    query = query_data.get("query", "").strip()

    if not query:
        raise HTTPException(status_code=422, detail={
            "error": "Query is required", "code": "VALIDATION_ERROR",
        })

    try:
        result = await answer_question(query, user_id, tier, crud)

        # Record query in history
        _query_history.append({
            "query": query,
            "user_id": user_id,
            "results_count": len(result.tool_calls),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Keep history manageable
        if len(_query_history) > 100:
            _query_history[:] = _query_history[-100:]

        return {
            "answer": result.answer,
            "tool_calls": result.tool_calls,
            "error": result.error,
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
