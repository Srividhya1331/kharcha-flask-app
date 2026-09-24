import csv
import io
from datetime import date

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import reports, services
from .extensions import db
from .models import Budget, Category, Expense
from .utils import csv_safe, current_month, paise_to_str, parse_month, shift_month

bp = Blueprint("main", __name__)


def _categories():
    stmt = db.select(Category).where(Category.user_id == current_user.id).order_by(Category.name)
    return db.session.scalars(stmt).all()


def _owned_expense_or_404(expense_id):
    # Filtering by user_id means another user's id looks exactly like a missing one.
    expense = db.session.scalar(
        db.select(Expense).where(Expense.id == expense_id, Expense.user_id == current_user.id)
    )
    if expense is None:
        abort(404, description="That expense doesn't exist.")
    return expense


@bp.route("/")
@login_required
def dashboard():
    month = parse_month(request.args.get("month")) or current_month()
    summary = reports.dashboard_summary(current_user.id, month)
    return render_template(
        "dashboard.html",
        month=month,
        prev_month=shift_month(month, -1),
        next_month=shift_month(month, 1),
        is_current=month == current_month(),
        recent=services.recent_expenses(current_user.id),
        **summary,
    )


@bp.route("/expenses")
@login_required
def expenses():
    page = db.paginate(
        services.build_expense_query(current_user.id, request.args),
        page=request.args.get("page", 1, type=int),
        per_page=10,
        error_out=False,
    )
    filters = {k: v for k, v in request.args.items() if k != "page" and v}
    return render_template(
        "expenses.html",
        page=page,
        filters=filters,
        categories=_categories(),
        total=services.filtered_total(current_user.id, request.args),
    )


@bp.route("/expenses/export.csv")
@login_required
def export_csv():
    rows = db.session.scalars(services.build_expense_query(current_user.id, request.args)).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Date", "Description", "Category", "Amount (INR)"])
    for e in rows:
        writer.writerow([e.spent_on.isoformat(), csv_safe(e.description), csv_safe(e.category.name),
                         paise_to_str(e.amount_paise)])
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


def _expense_form(expense):
    if request.method == "POST":
        data, errors = services.validate_expense(
            current_user.id,
            request.form.get("description"),
            request.form.get("amount"),
            request.form.get("spent_on"),
            request.form.get("category_id"),
        )
        if not errors:
            services.save_expense(current_user.id, data, expense)
            flash("Expense saved.", "success")
            return redirect(url_for("main.expenses"))
        values, status = request.form, 422
    else:
        status = 200
        values = (
            {"description": expense.description, "amount": paise_to_str(expense.amount_paise),
             "spent_on": expense.spent_on.isoformat(), "category_id": str(expense.category_id)}
            if expense else {"spent_on": date.today().isoformat()}
        )
        errors = {}
    return render_template("expense_form.html", expense=expense, categories=_categories(),
                           values=values, errors=errors), status


@bp.route("/expenses/new", methods=["GET", "POST"])
@login_required
def new_expense():
    return _expense_form(None)


@bp.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    return _expense_form(_owned_expense_or_404(expense_id))


@bp.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    db.session.delete(_owned_expense_or_404(expense_id))
    db.session.commit()
    flash("Expense deleted.", "success")
    return redirect(request.form.get("next") if request.form.get("next", "").startswith("/expenses")
                    else url_for("main.expenses"))


@bp.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    month = parse_month(request.values.get("month")) or current_month()
    categories = _categories()
    status = 200
    posted = None
    if request.method == "POST":
        errors = services.save_budgets(current_user.id, month, categories, request.form)
        if not errors:
            flash("Budgets saved.", "success")
            return redirect(url_for("main.budgets", month=month))
        for message in errors:
            flash(message, "error")
        posted, status = request.form, 422
    existing = {
        b.category_id: b
        for b in db.session.scalars(db.select(Budget).where(Budget.user_id == current_user.id, Budget.month == month))
    }
    return render_template(
        "budgets.html", month=month, prev_month=shift_month(month, -1), next_month=shift_month(month, 1),
        categories=categories, existing=existing, posted=posted, paise_to_str=paise_to_str,
    ), status
