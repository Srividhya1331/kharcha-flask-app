from datetime import date

from expense_tracker import reports
from expense_tracker.extensions import db
from expense_tracker.models import Budget, Category, Expense, User
from expense_tracker.services import seed_default_categories


def make_user(app):
    user = User(name="T", email="t@example.com", password_hash="x")
    db.session.add(user)
    db.session.flush()
    seed_default_categories(user)
    db.session.flush()
    cats = {c.name: c.id for c in db.session.scalars(db.select(Category))}
    return user, cats


def spend(user, cat_id, paise, when):
    db.session.add(Expense(user_id=user.id, category_id=cat_id, description="x", amount_paise=paise, spent_on=when))


def test_spend_by_category_groups_and_sorts(app):
    with app.app_context():
        user, cats = make_user(app)
        spend(user, cats["Food"], 10000, date(2026, 3, 5))
        spend(user, cats["Food"], 5000, date(2026, 3, 31))
        spend(user, cats["Rent"], 90000, date(2026, 3, 1))
        spend(user, cats["Food"], 99999, date(2026, 4, 1))  # next month: must be excluded
        db.session.commit()
        rows = reports.spend_by_category(user.id, "2026-03")
        assert [r["category"] for r in rows] == ["Rent", "Food"]
        assert rows[1]["total"] == 15000 and rows[1]["n"] == 2


def test_trend_fills_empty_months_across_year_end(app):
    with app.app_context():
        user, cats = make_user(app)
        spend(user, cats["Food"], 40000, date(2025, 12, 10))
        spend(user, cats["Food"], 20000, date(2026, 2, 10))
        db.session.commit()
        trend = reports.monthly_trend(user.id, "2026-02", months=3)
        assert [p["month"] for p in trend] == ["2025-12", "2026-01", "2026-02"]
        assert [p["total"] for p in trend] == [40000, 0, 20000]
        assert trend[0]["pct"] == 100 and trend[2]["pct"] == 50


def test_budget_status_levels(app):
    with app.app_context():
        user, cats = make_user(app)
        for name, limit in [("Food", 10000), ("Rent", 100000), ("Health", 5000)]:
            db.session.add(Budget(user_id=user.id, category_id=cats[name], month="2026-03", limit_paise=limit))
        spend(user, cats["Food"], 12000, date(2026, 3, 2))    # 120% -> over
        spend(user, cats["Rent"], 85000, date(2026, 3, 1))    # 85%  -> warn
        db.session.commit()                                    # Health: no spend -> ok
        status = {r["category"]: r for r in reports.budget_status(user.id, "2026-03")}
        assert status["Food"]["status"] == "over" and status["Food"]["pct"] == 100
        assert status["Rent"]["status"] == "warn"
        assert status["Health"]["status"] == "ok" and status["Health"]["spent"] == 0
        assert reports.budget_status(user.id, "2026-03")[0]["category"] == "Food"  # worst first


def test_reports_only_see_own_data(app):
    with app.app_context():
        user, cats = make_user(app)
        other = User(name="O", email="o@example.com", password_hash="x")
        db.session.add(other)
        db.session.flush()
        spend(user, cats["Food"], 1000, date(2026, 3, 1))
        db.session.commit()
        assert reports.month_total(other.id, "2026-03") == 0
