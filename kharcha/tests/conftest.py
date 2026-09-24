import pytest

from expense_tracker import create_app
from expense_tracker.config import TestConfig
from expense_tracker.extensions import db


class SecureTestConfig(TestConfig):
    CSRF_ENABLED = True


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="asha@example.com", name="Asha", password="password123"):
    return client.post("/register", data={"name": name, "email": email, "password": password, "confirm": password})


@pytest.fixture
def logged_in(client):
    register(client)
    return client


def first_category_id(app, email="asha@example.com"):
    from expense_tracker.models import Category, User
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == email))
        return db.session.scalars(db.select(Category).where(Category.user_id == user.id).order_by(Category.id)).first().id
