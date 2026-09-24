from datetime import date

from expense_tracker import create_app
from expense_tracker.extensions import db
from tests.conftest import SecureTestConfig, first_category_id, register


def test_api_requires_login(client):
    resp = client.get("/api/expenses")
    assert resp.status_code == 401
    assert resp.get_json()["error"]


def test_api_create_and_list(logged_in, app):
    payload = {"description": "Chai", "amount": 20, "spent_on": date.today().isoformat(),
               "category_id": first_category_id(app)}
    created = logged_in.post("/api/expenses", json=payload)
    assert created.status_code == 201
    assert created.get_json()["amount"] == "20.00"
    listing = logged_in.get("/api/expenses").get_json()
    assert listing["total"] == 1 and listing["items"][0]["description"] == "Chai"


def test_api_validation_returns_422(logged_in):
    resp = logged_in.post("/api/expenses", json={"description": "", "amount": "-1"})
    assert resp.status_code == 422
    assert {"description", "amount", "spent_on", "category_id"} <= set(resp.get_json()["errors"])


def test_api_rejects_non_json(logged_in):
    assert logged_in.post("/api/expenses", data="hello").status_code == 400


def test_api_summary_shape(logged_in):
    body = logged_in.get("/api/summary").get_json()
    assert {"month", "total", "by_category", "budgets", "trend"} <= set(body)
    assert len(body["trend"]) == 6


def test_csrf_blocks_posts_without_token():
    app = create_app(SecureTestConfig)
    client = app.test_client()
    resp = client.post("/register", data={"name": "A", "email": "a@example.com",
                                          "password": "password123", "confirm": "password123"})
    assert resp.status_code == 400
    with app.app_context():
        db.drop_all()


def test_csrf_accepts_valid_token():
    app = create_app(SecureTestConfig)
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["csrf_token"] = "abc123"
    resp = client.post("/register", data={"csrf_token": "abc123", "name": "A", "email": "a@example.com",
                                          "password": "password123", "confirm": "password123"})
    assert resp.status_code == 302
    with app.app_context():
        db.drop_all()
