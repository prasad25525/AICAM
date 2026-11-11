def test_health_is_public(client):
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}


def test_login_success_and_me(client, auth):
    assert client.get("/api/auth/me", headers=auth).json() == {"username": "admin"}


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_protected_routes_need_token(client):
    for path in ("/api/cameras", "/api/system/info", "/api/auth/me"):
        assert client.get(path).status_code == 401


def test_bad_and_tampered_tokens_rejected(client, auth):
    assert client.get("/api/cameras", headers={"Authorization": "Bearer abc.def"}).status_code == 401
    token = auth["Authorization"].removeprefix("Bearer ")
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert client.get("/api/cameras", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
