"""Analytics written as hand-written SQL (GROUP BY, JOIN, subquery, COALESCE).

Date filters use a half-open range (>= start AND < end) instead of
strftime() on the column, so SQLite can use the (user_id, spent_on) index.
"""
from sqlalchemy import text

from .extensions import db
from .utils import month_bounds, month_label, shift_month


def _rows(sql, params):
    return [dict(row._mapping) for row in db.session.execute(text(sql), params)]


def _range(month):
    start, end = month_bounds(month)
    return start.isoformat(), end.isoformat()


def month_total(user_id, month):
    start, end = _range(month)
    sql = """
        SELECT COALESCE(SUM(amount_paise), 0) AS total
        FROM expenses
        WHERE user_id = :uid AND spent_on >= :start AND spent_on < :end
    """
    return db.session.execute(text(sql), {"uid": user_id, "start": start, "end": end}).scalar()


def spend_by_category(user_id, month):
    start, end = _range(month)
    sql = """
        SELECT c.name AS category, SUM(e.amount_paise) AS total, COUNT(*) AS n
        FROM expenses e
        JOIN categories c ON c.id = e.category_id
        WHERE e.user_id = :uid AND e.spent_on >= :start AND e.spent_on < :end
        GROUP BY c.id, c.name
        ORDER BY total DESC
    """
    return _rows(sql, {"uid": user_id, "start": start, "end": end})


def monthly_trend(user_id, end_month, months=6):
    """Last N months ending at end_month. Months with no spend are filled with 0
    (a plain GROUP BY would silently skip them and squash the chart)."""
    first = shift_month(end_month, -(months - 1))
    start = month_bounds(first)[0].isoformat()
    end = month_bounds(end_month)[1].isoformat()
    sql = """
        SELECT strftime('%Y-%m', spent_on) AS month, SUM(amount_paise) AS total
        FROM expenses
        WHERE user_id = :uid AND spent_on >= :start AND spent_on < :end
        GROUP BY month
    """
    totals = {r["month"]: r["total"] for r in _rows(sql, {"uid": user_id, "start": start, "end": end})}
    series = []
    for i in range(months):
        m = shift_month(first, i)
        series.append({"month": m, "label": month_label(m, short=True), "total": totals.get(m, 0)})
    peak = max((p["total"] for p in series), default=0)
    for p in series:
        p["pct"] = round(p["total"] * 100 / peak) if peak else 0
    return series


def budget_status(user_id, month):
    """Each budget with how much has been spent; worst offenders first."""
    start, end = _range(month)
    sql = """
        SELECT c.name AS category,
               b.limit_paise AS budget_limit,
               COALESCE(s.spent, 0) AS spent
        FROM budgets b
        JOIN categories c ON c.id = b.category_id
        LEFT JOIN (
            SELECT category_id, SUM(amount_paise) AS spent
            FROM expenses
            WHERE user_id = :uid AND spent_on >= :start AND spent_on < :end
            GROUP BY category_id
        ) s ON s.category_id = b.category_id
        WHERE b.user_id = :uid AND b.month = :month
        ORDER BY COALESCE(s.spent, 0) * 1.0 / b.limit_paise DESC
    """
    rows = _rows(sql, {"uid": user_id, "start": start, "end": end, "month": month})
    for r in rows:
        ratio = r["spent"] * 100 / r["budget_limit"]
        r["pct"] = min(round(ratio), 100)
        r["remaining"] = r["budget_limit"] - r["spent"]
        r["status"] = "over" if r["spent"] > r["budget_limit"] else "warn" if ratio >= 80 else "ok"
    return rows


def dashboard_summary(user_id, month):
    by_category = spend_by_category(user_id, month)
    total = sum(r["total"] for r in by_category)
    for r in by_category:
        r["pct"] = round(r["total"] * 100 / total) if total else 0
    return {
        "total": total,
        "prev_total": month_total(user_id, shift_month(month, -1)),
        "by_category": by_category,
        "budgets": budget_status(user_id, month),
        "trend": monthly_trend(user_id, month),
    }
