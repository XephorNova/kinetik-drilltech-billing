async def test_login_with_correct_credentials_sets_cookie(client):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "adminpass123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.cookies


async def test_login_with_wrong_password_rejected(client):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "wrongpass"}
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_returns_username_when_authenticated(authed_client):
    resp = await authed_client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"username": "admin"}


async def test_logout_clears_cookie(authed_client):
    resp = await authed_client.post("/auth/logout")
    assert resp.status_code == 200
    me_resp = await authed_client.get("/auth/me")
    assert me_resp.status_code == 401
