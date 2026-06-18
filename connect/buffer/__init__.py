"""Buffer module — SQLite-backed offline queue for trigger events.

Provides local buffering when the internet connection is down.
Events are queued with a 48-hour TTL and flushed to the backend
when connectivity is restored.
"""
