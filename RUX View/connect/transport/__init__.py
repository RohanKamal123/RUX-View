"""Transport module — outbound WebSocket, HTTPS trigger sender, SMS fallback.

All connections are outbound only (solves NAT — D009).
Trigger-only architecture — no continuous streaming (D005).
"""
