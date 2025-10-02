from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Shared properties
class ActivityLogBase(BaseModel):
    timestamp: datetime
    app: str
    window: str
    keys: int
    clicks: int
    movements: int
    idle: bool
    screenshot: Optional[str] = None
    reason: Optional[str] = None

# Properties to receive on item creation
class ActivityLogCreate(ActivityLogBase):
    pass

# Properties to return to client
class ActivityLogOut(ActivityLogBase):
    id: int

    class Config:
        from_attributes = True
