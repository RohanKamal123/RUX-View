from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, text

API_KEY = "PUT_API_KEY_HERE"
DB_URL = "postgresql://user:password@localhost:5432/timetracker"  # or sqlite:///server.db for small setup

engine = create_engine(DB_URL, echo=False)
app = FastAPI()

class Record(BaseModel):
    employee_id: str
    app_name: str
    active_seconds: int
    idle_seconds: int
    date: str
    timestamp: str

class Batch(BaseModel):
    records: List[Record]

@app.post("/ingest")
def ingest(batch: Batch, authorization: str = Header(None)):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid API key")
    rows = []
    for r in batch.records:
        rows.append((r.employee_id, r.app_name, r.active_seconds, r.idle_seconds, r.date, r.timestamp))
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS activity (
                id SERIAL PRIMARY KEY,
                employee_id TEXT,
                app_name TEXT,
                active_seconds INTEGER,
                idle_seconds INTEGER,
                date DATE,
                created_at TIMESTAMP WITH TIME ZONE
            )
        """))
        conn.executemany(text("""
            INSERT INTO activity (employee_id, app_name, active_seconds, idle_seconds, date, created_at)
            VALUES (:e, :a, :act, :idle, :d, :c)
        """), [{"e":r[0],"a":r[1],"act":r[2],"idle":r[3],"d":r[4],"c":r[5]} for r in rows])
    return {"status":"ok", "inserted": len(rows)}