def login(client, username="admin", password="admin123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_success_returns_token(client):
    res = login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(client):
    res = login(client, password="nope")
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid username or password"


def test_login_unknown_user(client):
    assert login(client, username="ghost").status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_bad_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert res.status_code == 401


def test_me_with_token(client):
    token = login(client).json()["access_token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["username"] == "admin"
