"""Debug script to check dashboard routes without overrides."""
from fastapi.testclient import TestClient
from backend.dashboard.server import app

# Clear all overrides
app.dependency_overrides.clear()

client = TestClient(app)

# Test each route
routes = ['/', '/camera/cam_001', '/settings', '/payment', '/person/PERSON_A1B2']
for route in routes:
    response = client.get(route)
    print(f'GET {route} -> Status: {response.status_code}')
    if response.status_code != 200:
        print(f'  Body: {response.text[:500]}')
    print()
