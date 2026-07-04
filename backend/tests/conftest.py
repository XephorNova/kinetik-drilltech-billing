import os
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass123")

import pytest
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

from app.main import app
from app.database import get_db


@pytest.fixture
def mock_db():
    mongo_client = AsyncMongoMockClient()
    return mongo_client["test_billing"]


@pytest.fixture
def override_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client(override_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client(client):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "adminpass123"}
    )
    assert resp.status_code == 200
    return client
