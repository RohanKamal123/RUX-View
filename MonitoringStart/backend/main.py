import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import List
from datetime import datetime

from . import crud, models, schemas
from .database.db import engine, Base, get_db

load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup():
    # create db tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# CORS Middleware
from fastapi.middleware.cors import CORSMiddleware

origins = []
CORS_ORIGINS = os.getenv('CORS_ORIGINS')
if CORS_ORIGINS:
    origins.extend(CORS_ORIGINS.split(','))
else: # Default for local dev
    origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/logs/", response_model=schemas.ActivityLogOut)
async def create_log_entry(log: schemas.ActivityLogCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_log(db=db, log=log)

@app.get("/logs/", response_model=List[schemas.ActivityLogOut])
async def read_logs(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    logs = await crud.get_logs(db, skip=skip, limit=limit)
    return logs

@app.get("/logs/search", response_model=List[schemas.ActivityLogOut])
async def search_logs_by_app(app: str, db: AsyncSession = Depends(get_db)):
    logs = await crud.get_logs_by_app(db, app=app)
    return logs

@app.get("/logs/{id}", response_model=schemas.ActivityLogOut)
async def read_log(id: int, db: AsyncSession = Depends(get_db)):
    db_log = await crud.get_log(db, id=id)
    if db_log is None:
        raise HTTPException(status_code=404, detail="Log not found")
    return db_log

# NEW ENDPOINTS FOR FRONTEND

@app.get("/api/logs/daily")
async def get_daily_summary(db: AsyncSession = Depends(get_db)):
    """Get daily summary of activity logs"""
    try:
        # Query to get daily summaries
        query = select(
            func.date(models.ActivityLog.timestamp).label('date'),
            func.count(models.ActivityLog.id).label('activity_count'),
            func.count(models.ActivityLog.screenshot).label('screenshot_count')
        ).group_by(
            func.date(models.ActivityLog.timestamp)
        ).order_by(
            func.date(models.ActivityLog.timestamp).desc()
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        # Format the response
        daily_summaries = [
            {
                "date": str(row.date),
                "activity_count": row.activity_count,
                "screenshot_count": row.screenshot_count
            }
            for row in rows
        ]
        
        return daily_summaries
    except Exception as e:
        print(f"Error in get_daily_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs/detail/{date}")
async def get_log_details(date: str, db: AsyncSession = Depends(get_db)):
    """Get detailed logs for a specific date"""
    try:
        # Parse the date string
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Query logs for the specific date
        query = select(models.ActivityLog).where(
            func.date(models.ActivityLog.timestamp) == target_date
        ).order_by(models.ActivityLog.timestamp)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        # Format the response
        entries = [
            {
                "timestamp": log.timestamp.strftime("%H:%M:%S"),
                "event_type": "screenshot" if log.screenshot is not None else "activity",
                "window_title": log.window or "N/A"
            }
            for log in logs
        ]
        
        return {
            "date": date,
            "entries": entries
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_log_details: {e}")
        raise HTTPException(status_code=500, detail=str(e))