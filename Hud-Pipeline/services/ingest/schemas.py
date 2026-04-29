from pydantic import BaseModel
from typing import Optional
import datetime

class NewsOut(BaseModel):
    id: int
    source: str
    title: str
    url: str
    published_at: Optional[datetime.datetime] = None
    fetched_at: datetime.datetime

    class Config:
        from_attributes = True  # For SQLAlchemy compatibility (v2+)