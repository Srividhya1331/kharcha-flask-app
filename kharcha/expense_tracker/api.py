"""Small JSON API. Uses the same session login + CSRF header (X-CSRF-Token) as the site."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from . import reports, services
from .extensions import db
from .utils import current_month, parse_month

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/expenses")
@login_required
def list_expenses():
    page = db.paginate(
        services.build_expense_query(current_user.id, request.args),
        page=request.args.get("page", 1, type=int),
        per_page=min(request.args.get("per_page", 20, type=int), 100),
        error_out=False,
    )
    return jsonify(items=[e.to_dict() for e in page.items], page=page.page, pages=page.pages, total=page.total)


@bp.post("/expenses")
@login_required
def create_expense():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Send a JSON object."), 400
    data, errors = services.validate_expense(
        current_user.id, payload.get("description"), payload.get("amount"),
        payload.get("spent_on"), payload.get("category_id"),
    )
    if errors:
        return jsonify(errors=errors), 422
    return jsonify(services.save_expense(current_user.id, data).to_dict()), 201


@bp.get("/summary")
@login_required
def summary():
    month = parse_month(request.args.get("month")) or current_month()
    return jsonify(month=month, **reports.dashboard_summary(current_user.id, month))
