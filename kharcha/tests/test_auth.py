from tests.conftest import register


def test_register_logs_in_and_seeds_categories(client):
    resp = register(client)
    assert resp.status_code == 302
    page = client.get("/expenses/new")
    assert b"Food" in page.data and b"Rent" in page.data


def test_duplicate_email_rejected(client):
    register(client)
    client.post("/logout")
    resp = register(client)
    assert resp.status_code == 422
    assert b"already exists" in resp.data


def test_short_password_rejected(client):
    resp = register(client, password="short")
    assert resp.status_code == 422


def test_login_wrong_password(client):
    register(client)
    client.post("/logout")
    resp = client.post("/login", data={"email": "asha@example.com", "password": "nope-nope"})
    assert resp.status_code == 401
    assert b"incorrect" in resp.data


def test_login_and_logout(client):
    register(client)
    client.post("/logout")
    assert client.get("/").status_code == 302  # redirected to login
    resp = client.post("/login", data={"email": "ASHA@example.com", "password": "password123"})
    assert resp.status_code == 302
    assert client.get("/").status_code == 200


def test_login_blocks_open_redirect(client):
    register(client)
    client.post("/logout")
    resp = client.post("/login?next=//evil.com", data={"email": "asha@example.com", "password": "password123"})
    assert resp.headers["Location"] == "/"


def test_login_required(client):
    assert client.get("/expenses").status_code == 302
