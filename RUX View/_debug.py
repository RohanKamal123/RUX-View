"""Debug script to check dashboard routes."""
import asyncio
from fastapi.testclient import TestClient
from backend.dashboard.server import app, get_current_user

# Override with mock
async def mock_get_user(request):
    return {'user_id': 'user_001', 'email': 'test@example.com', 'tier': 'household', 'name': 'Test User'}

app.dependency_overrides[get_current_user] = mock_get_user

client = TestClient(app)

# Test each route
routes = ['/', '/camera/cam_001', '/settings', '/payment', '/person/PERSON_A1B2']
for route in routes:
    response = client.get(route)
    print(f'GET {route} -> Status: {response.status_code}')
    if response.status_code != 200:
        print(f'  Body: {response.text[:500]}')
    print()
