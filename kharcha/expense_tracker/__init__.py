import secrets
import sqlite3

import click
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import db, login_manager
from .utils import format_inr, get_csrf_token, month_label


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    # SQLite ignores foreign keys unless you switch them on per connection.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Log in to continue."
    login_manager.login_message_category = "info"

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Authentication required."), 401
        return redirect(url_for("auth.login", next=request.path))

    @app.before_request
    def protect_against_csrf():
        if not app.config["CSRF_ENABLED"] or request.method in ("GET", "HEAD", "OPTIONS"):
            return
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
        expected = session.get("csrf_token") or ""
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400, description="Your session expired. Reload the page and try again.")

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        if request.path.startswith("/api/"):
            return jsonify(error=err.description), err.code
        return render_template("error.html", code=err.code, message=err.description), err.code

    app.jinja_env.globals["csrf_token"] = get_csrf_token
    app.jinja_env.filters["inr"] = format_inr
    app.jinja_env.filters["month_label"] = month_label

    from . import api, auth, main

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)

    with app.app_context():
        db.create_all()

    register_cli(app)
    return app


def register_cli(app):
    @app.cli.command("seed-demo")
    def seed_demo():
        """Create demo@example.com (password: demo12345) with six months of sample data."""
        import random
        from datetime import date, timedelta

        from .models import Budget, Category, Expense, User
        from .services import seed_default_categories
        from .utils import current_month

        if db.session.scalar(db.select(User).where(User.email == "demo@example.com")):
            click.echo("Demo user already exists.")
            return
        user = User(name="Demo User", email="demo@example.com")
        user.set_password("demo12345")
        db.session.add(user)
        db.session.flush()
        seed_default_categories(user)
        db.session.flush()

        cats = {c.name: c.id for c in db.session.scalars(db.select(Category).where(Category.user_id == user.id))}
        rng = random.Random(42)  # fixed seed -> same demo data every time
        samples = {
            "Food": (["Swiggy order", "Groceries", "Filter coffee", "Lunch"], 120, 900),
            "Transport": (["Metro recharge", "Uber", "Petrol"], 60, 1200),
            "Shopping": (["Amazon", "Myntra", "Headphones"], 300, 3500),
            "Utilities": (["Electricity bill", "Broadband", "Mobile recharge"], 300, 1500),
            "Entertainment": (["Movie tickets", "Netflix", "Concert"], 200, 1800),
            "Health": (["Pharmacy", "Gym membership"], 150, 2000),
        }
        today = date.today()
        for days_ago in range(180):
            day = today - timedelta(days=days_ago)
            if day.day == 1:
                db.session.add(Expense(user_id=user.id, category_id=cats["Rent"], description="Monthly rent",
                                       amount_paise=18000 * 100, spent_on=day))
            for _ in range(rng.choice([0, 0, 1, 1, 2])):
                name = rng.choice(list(samples))
                labels, low, high = samples[name]
                db.session.add(Expense(user_id=user.id, category_id=cats[name], description=rng.choice(labels),
                                       amount_paise=rng.randint(low, high) * 100, spent_on=day))
        month = current_month()
        for name, limit in {"Food": 6000, "Shopping": 3000, "Transport": 2500, "Entertainment": 2000}.items():
            db.session.add(Budget(user_id=user.id, category_id=cats[name], month=month, limit_paise=limit * 100))
        db.session.commit()
        click.echo("Created demo@example.com / demo12345")
