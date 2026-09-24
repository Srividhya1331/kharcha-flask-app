from datetime import date, timedelta

from expense_tracker.extensions import db
from expense_tracker.models import Expense
from tests.conftest import first_category_id, register


def add(client, app, description="Lunch", amount="250.50", spent_on=None, category_id=None):
    return client.post("/expenses/new", data={
        "description": description, "amount": amount,
        "spent_on": spent_on or date.today().isoformat(),
        "category_id": category_id or first_category_id(app),
    })


def test_create_expense_stores_paise(logged_in, app):
    assert add(logged_in, app).status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(Expense)).amount_paise == 25050


def test_validation_errors_keep_input(logged_in, app):
    resp = add(logged_in, app, description="  ", amount="abc", spent_on="2999-01-01")
    assert resp.status_code == 422
    for message in (b"Enter a description", b"must be a number", b"in the future"):
        assert message in resp.data


def test_cannot_use_another_users_category(client, app):
    register(client, email="a@example.com")
    other_category = first_category_id(app, "a@example.com")
    client.post("/logout")
    register(client, email="b@example.com")
    resp = add(client, app, category_id=other_category)
    assert resp.status_code == 422
    assert b"Choose a category" in resp.data


def test_users_cannot_touch_each_others_expenses(client, app):
    register(client, email="a@example.com")
    add(client, app, category_id=first_category_id(app, "a@example.com"))
    client.post("/logout")
    register(client, email="b@example.com")
    assert client.get("/expenses/1/edit").status_code == 404
    assert client.post("/expenses/1/delete").status_code == 404
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Expense.id))) == 1


def test_edit_and_delete(logged_in, app):
    add(logged_in, app)
    resp = logged_in.post("/expenses/1/edit", data={
        "description": "Dinner", "amount": "600", "spent_on": date.today().isoformat(),
        "category_id": first_category_id(app)})
    assert resp.status_code == 302
    assert b"Dinner" in logged_in.get("/expenses").data
    logged_in.post("/expenses/1/delete")
    assert b"No expenses yet" in logged_in.get("/expenses").data


def test_search_treats_percent_literally(logged_in, app):
    add(logged_in, app, description="Sale 50% off")
    add(logged_in, app, description="Coffee")
    page = logged_in.get("/expenses?q=%25").data
    assert b"Sale 50% off" in page and b"Coffee" not in page


def test_month_filter_and_pagination(logged_in, app):
    for i in range(12):
        add(logged_in, app, description=f"Item {i}")
    assert b"Page 1 of 2" in logged_in.get("/expenses").data
    assert b"Item 0" in logged_in.get("/expenses?page=2").data
    last_month = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    assert b"No expenses match" in logged_in.get(f"/expenses?month={last_month}").data


def test_csv_export_neutralises_formulas(logged_in, app):
    add(logged_in, app, description="=HYPERLINK(\"http://evil\")")
    resp = logged_in.get("/expenses/export.csv")
    assert resp.mimetype == "text/csv"
    assert b"'=HYPERLINK" in resp.data
    assert b"250.50" in resp.data
