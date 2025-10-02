from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from . import models, schemas

async def get_log(db: AsyncSession, id: int):
    result = await db.execute(select(models.ActivityLog).filter(models.ActivityLog.id == id))
    return result.scalars().first()

async def get_logs(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(models.ActivityLog).offset(skip).limit(limit))
    return result.scalars().all()

async def create_log(db: AsyncSession, log: schemas.ActivityLogCreate):
    db_log = models.ActivityLog(**log.dict())
    db.add(db_log)
    await db.commit()
    await db.refresh(db_log)
    return db_log

async def get_logs_by_app(db: AsyncSession, app: str):
    result = await db.execute(select(models.ActivityLog).filter(models.ActivityLog.app == app))
    return result.scalars().all()
