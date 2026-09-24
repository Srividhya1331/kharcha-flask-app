from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .utils import paise_to_str

DEFAULT_CATEGORIES = [
    "Food", "Rent", "Transport", "Utilities",
    "Shopping", "Health", "Entertainment", "Other",
]


def _now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(40), nullable=False)


class Expense(db.Model):
    __tablename__ = "expenses"
    __table_args__ = (
        db.CheckConstraint("amount_paise > 0", name="ck_expense_amount_positive"),
        db.Index("ix_expenses_user_date", "user_id", "spent_on"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount_paise = db.Column(db.Integer, nullable=False)
    spent_on = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=_now, nullable=False)

    category = db.relationship("Category")

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "amount": paise_to_str(self.amount_paise),
            "amount_paise": self.amount_paise,
            "spent_on": self.spent_on.isoformat(),
            "category": {"id": self.category.id, "name": self.category.name},
        }


class Budget(db.Model):
    __tablename__ = "budgets"
    __table_args__ = (
        db.UniqueConstraint("user_id", "category_id", "month", name="uq_budget_user_cat_month"),
        db.CheckConstraint("limit_paise > 0", name="ck_budget_limit_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # 'YYYY-MM'
    limit_paise = db.Column(db.Integer, nullable=False)
