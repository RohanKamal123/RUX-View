import asyncio
import os
import sys
from datetime import datetime, timedelta

# -- Path Setup --
# Add the project root to the Python path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.database.db import engine, get_db
from backend.models import ActivityLog
from backend.database.base import Base

async def initialize_database():
    """Connects to the database, creates all tables, and adds sample data."""
    print("Connecting to the database and creating tables...")
    async with engine.begin() as conn:
        # Drop all tables first to ensure a clean slate
        await conn.run_sync(Base.metadata.drop_all)
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")

    print("Adding sample data...")
    # Use a session to add data
    async for db in get_db():
        # Clear existing data to avoid duplicates on re-runs
        await db.execute(ActivityLog.__table__.delete())

        # Add some sample data
        sample_logs = [
            ActivityLog(timestamp=datetime.now() - timedelta(days=1), app="VS Code", window="monitoring/App.jsx", keys=120, clicks=30, movements=500),
            ActivityLog(timestamp=datetime.now() - timedelta(days=1, hours=1), app="Chrome", window="localhost:5173", keys=50, clicks=10, movements=200, screenshot="screenshot1.png"),
            ActivityLog(timestamp=datetime.now() - timedelta(days=2), app="Photoshop", window="new_design.psd", keys=200, clicks=50, movements=1000),
            ActivityLog(timestamp=datetime.now() - timedelta(days=2, hours=2), app="Photoshop", window="new_design.psd", keys=10, clicks=5, movements=50, idle=True),
        ]
        db.add_all(sample_logs)
        await db.commit()
        break # Exit after one iteration
    print("Sample data added successfully.")

if __name__ == "__main__":
    asyncio.run(initialize_database())