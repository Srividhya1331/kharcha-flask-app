import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User
from .services import seed_default_categories
from .utils import is_safe_redirect

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    errors, values = {}, request.form
    if request.method == "POST":
        name = (values.get("name") or "").strip()
        email = (values.get("email") or "").strip().lower()
        password = values.get("password") or ""
        if not name:
            errors["name"] = "Enter your name."
        if not EMAIL_RE.match(email):
            errors["email"] = "Enter a valid email address."
        elif db.session.scalar(db.select(User).where(User.email == email)):
            errors["email"] = "An account with this email already exists. Log in instead."
        if len(password) < 8:
            errors["password"] = "Use at least 8 characters."
        elif password != values.get("confirm"):
            errors["confirm"] = "Passwords don't match."
        if not errors:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # get user.id before seeding categories
            seed_default_categories(user)
            db.session.commit()
            login_user(user)
            flash(f"Welcome, {name}. Add your first expense to get started.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("register.html", errors=errors, values=values), 422 if errors else 200


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = db.session.scalar(db.select(User).where(User.email == email))
        if user and user.check_password(request.form.get("password") or ""):
            login_user(user)
            target = request.args.get("next")
            return redirect(target if is_safe_redirect(target) else url_for("main.dashboard"))
        error = "Email or password is incorrect."  # same message for both cases: no user enumeration
    return render_template("login.html", error=error), 401 if error else 200


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You're logged out.", "info")
    return redirect(url_for("auth.login"))
