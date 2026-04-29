from sqlalchemy import Boolean, Column, Integer, String, DateTime
from .database.base import Base

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime)
    app = Column(String, index=True)
    window = Column(String)
    keys = Column(Integer)
    clicks = Column(Integer)
    movements = Column(Integer)
    idle = Column(Boolean, default=False)
    screenshot = Column(String, nullable=True)
    reason = Column(String, nullable=True)
