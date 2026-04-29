# services/ingest/schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NewsOut(BaseModel):
    id: int
    source: str
    title: str
    url: str
    published_at: Optional[datetime]
    fetched_at: datetime
    summary: Optional[str]

    class Config:
        orm_mode = True
