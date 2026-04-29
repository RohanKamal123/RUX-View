import os
import json
from typing import Optional
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer, BadSignature
from database import get_recent_visitors, get_stats, toggle_star, get_names, get_sessions, save_name

app = FastAPI()
templates = Jinja2Templates(directory="templates")

SNAPSHOT_DIR = "snapshots"
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin123")
serializer = URLSafeSerializer(SECRET_KEY)
SESSION_COOKIE = "cctv_session"

os.makedirs(SNAPSHOT_DIR, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")


# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        return serializer.loads(token, max_age=86400)
    except BadSignature:
        return None


def require_auth(request: Request):
    if not get_session(request):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    if form.get("password") == PASSWORD:
        token = serializer.dumps("authenticated")
        resp = RedirectResponse(url="/", status_code=302)
        resp.set_cookie(SESSION_COOKIE, token, httponly=True, max_age=86400)
        return resp
    return templates.TemplateResponse("login.html", {"request": request, "error": "Wrong password"})


@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    require_auth(request)
    visitors = get_recent_visitors(limit=30)
    stats = get_stats()

    with open("cameras.json") as f:
        cameras = json.load(f)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "visitors": visitors,
        "stats": stats,
        "cameras": cameras,
    })


@app.get("/api/visitors")
async def api_visitors(request: Request, camera_id: Optional[int] = None, limit: int = 20):
    require_auth(request)
    visitors = get_recent_visitors(limit=limit)
    if camera_id is not None:
        visitors = [v for v in visitors if v["camera_id"] == camera_id]
    return visitors


@app.get("/api/stats")
async def api_stats(request: Request):
    require_auth(request)
    return get_stats()


@app.get("/snapshots/{filename}")
async def serve_snapshot(filename: str, request: Request):
    require_auth(request)
    path = os.path.join(SNAPSHOT_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path)

@app.post("/api/name/{session_id}")
async def api_save_name(session_id: int, request: Request):
    require_auth(request)
    body = await request.json()
    save_name(session_id, body.get("name", "").strip())
    return {"ok": True}


@app.post("/api/star/{session_id}")
async def api_toggle_star(session_id: int, request: Request):
    require_auth(request)
    starred = toggle_star(session_id)
    return {"starred": starred}


@app.get("/persons", response_class=HTMLResponse)
async def persons_page(request: Request):
    require_auth(request)
    names = get_names()
    sessions = get_sessions(limit=200)

    seen = {}
    for s in sessions:
        name = names.get(s["id"])
        if name and name not in seen:
            seen[name] = {
                "name": name,
                "visit_count": 0,
                "last_seen": s["timestamp"],
                "snapshot_path": s["snapshot_path"],
            }
        if name:
            seen[name]["visit_count"] += 1

    return templates.TemplateResponse("persons.html", {
        "request": request,
        "persons": list(seen.values()),
    })