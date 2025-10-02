import os
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

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