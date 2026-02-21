def test_signup_creates_user(client):
    response = client.post(
        "/api/auth/signup",
        json={"email": "newuser@winnow.dev", "password": "SecurePass123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@winnow.dev"
    # Check auth cookie was set
    assert "rm_session" in response.headers.get("set-cookie", "")


def test_signup_duplicate_email_fails(client):
    client.post(
        "/api/auth/signup",
        json={"email": "dup@winnow.dev", "password": "Pass123!"},
    )
    response = client.post(
        "/api/auth/signup",
        json={"email": "dup@winnow.dev", "password": "Pass456!"},
    )
    assert response.status_code in (400, 409)


def test_login_valid_credentials(client):
    client.post(
        "/api/auth/signup",
        json={"email": "login@winnow.dev", "password": "Pass123!"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "login@winnow.dev", "password": "Pass123!"},
    )
    assert response.status_code == 200
    assert "rm_session" in response.headers.get("set-cookie", "")


def test_login_wrong_password(client):
    client.post(
        "/api/auth/signup",
        json={"email": "wrong@winnow.dev", "password": "Pass123!"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "wrong@winnow.dev", "password": "WrongPass!"},
    )
    assert response.status_code == 401


def test_me_returns_user_info(auth_client):
    client, user = auth_client
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_me_unauthenticated_fails(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_logout_clears_cookie(auth_client):
    client, _ = auth_client
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
