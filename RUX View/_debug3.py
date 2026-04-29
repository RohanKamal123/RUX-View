import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock
from backend.core.health_checker import HealthChecker

async def test():
    mock_factory = MagicMock()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_factory.return_value.__aenter__.return_value = mock_session
    mock_factory.return_value.__aexit__.return_value = None
    
    checker = HealthChecker(
        db_session_factory=mock_factory,
        ai_client=MagicMock(),
        groq_client=MagicMock(),
        telegram_client=MagicMock(),
    )
    
    result = await checker.check_all()
    print(f'Status: {result["status"]}', flush=True)
    for k, v in result['checks'].items():
        print(f'  {k}: {v["status"]} - {v.get("error")}', flush=True)

try:
    asyncio.run(test())
except Exception as e:
    print(f'ERROR: {e}', flush=True)
    import traceback
    traceback.print_exc()
