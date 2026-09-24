"""Business logic shared by the HTML routes and the JSON API."""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from .extensions import db
from .models import DEFAULT_CATEGORIES, Budget, Category, Expense
from .utils import month_bounds, parse_amount_to_paise, parse_month


def seed_default_categories(user):
    for name in DEFAULT_CATEGORIES:
        db.session.add(Category(user_id=user.id, name=name))


# ---------- expenses ----------
def validate_expense(user_id, description, amount, spent_on, category_id):
    """Return (clean_data, errors). Never trusts the client, including category_id."""
    errors = {}
    data = {}

    description = description.strip() if isinstance(description, str) else ""
    if not description:
        errors["description"] = "Enter a description."
    elif len(description) > 200:
        errors["description"] = "Keep the description under 200 characters."
    data["description"] = description

    try:
        data["amount_paise"] = parse_amount_to_paise("" if amount is None else str(amount))
    except ValueError as exc:
        errors["amount"] = str(exc)

    try:
        parsed = date.fromisoformat(str(spent_on or ""))
        if parsed > date.today():
            errors["spent_on"] = "The date can't be in the future."
        data["spent_on"] = parsed
    except ValueError:
        errors["spent_on"] = "Enter a valid date."

    try:
        cid = int(category_id)
    except (TypeError, ValueError):
        cid = None
    category = db.session.get(Category, cid) if cid is not None else None
    if category is None or category.user_id != user_id:
        errors["category_id"] = "Choose a category."
    else:
        data["category_id"] = category.id

    return data, errors


def save_expense(user_id, data, expense=None):
    if expense is None:
        expense = Expense(user_id=user_id)
        db.session.add(expense)
    expense.description = data["description"]
    expense.amount_paise = data["amount_paise"]
    expense.spent_on = data["spent_on"]
    expense.category_id = data["category_id"]
    db.session.commit()
    return expense


def _filters(user_id, args):
    conditions = [Expense.user_id == user_id]
    month = parse_month(args.get("month"))
    if month:
        start, end = month_bounds(month)
        conditions += [Expense.spent_on >= start, Expense.spent_on < end]
    try:
        category_id = int(args.get("category") or "")
        conditions.append(Expense.category_id == category_id)
    except ValueError:
        pass
    search = (args.get("q") or "").strip()
    if search:
        # autoescape=True treats % and _ typed by the user as literal characters
        conditions.append(Expense.description.contains(search, autoescape=True))
    return conditions


def build_expense_query(user_id, args):
    return (
        db.select(Expense)
        .options(joinedload(Expense.category))  # avoids one query per row (N+1)
        .where(*_filters(user_id, args))
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
    )


def filtered_total(user_id, args):
    stmt = db.select(func.coalesce(func.sum(Expense.amount_paise), 0)).where(*_filters(user_id, args))
    return db.session.scalar(stmt)


def recent_expenses(user_id, limit=5):
    stmt = build_expense_query(user_id, {}).limit(limit)
    return db.session.scalars(stmt).all()


# ---------- budgets ----------
def save_budgets(user_id, month, categories, form):
    """Blank field = no budget. All-or-nothing: nothing is saved if any field is invalid."""
    parsed, errors = {}, []
    for cat in categories:
        raw = (form.get(f"limit_{cat.id}") or "").strip()
        if not raw:
            parsed[cat.id] = None
            continue
        try:
            parsed[cat.id] = parse_amount_to_paise(raw)
        except ValueError as exc:
            errors.append(f"{cat.name}: {exc}")
    if errors:
        return errors

    existing = {
        b.category_id: b
        for b in db.session.scalars(db.select(Budget).where(Budget.user_id == user_id, Budget.month == month))
    }
    for cat_id, limit in parsed.items():
        budget = existing.get(cat_id)
        if limit is None:
            if budget:
                db.session.delete(budget)
        elif budget:
            budget.limit_paise = limit
        else:
            db.session.add(Budget(user_id=user_id, category_id=cat_id, month=month, limit_paise=limit))
    db.session.commit()
    return []
