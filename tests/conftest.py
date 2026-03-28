import os
import sys
import pytest

# ====================== ИСПРАВЛЕНИЕ ИМПОРТА ======================
# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app as flask_app, db
from app import User, Product


@pytest.fixture(scope="session")
def app():
    """Создаём тестовое приложение"""
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SECRET_KEY": "test_secret_key_12345",
        "WTF_CSRF_ENABLED": False,
        "MAIL_SUPPRESS_SEND": True,
    })
    return flask_app


@pytest.fixture(scope="function")
def client(app):
    """Тестовый клиент"""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app):
    """Изолированная БД для каждого теста"""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        db.drop_all()