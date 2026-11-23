"""Спільні фікстури: окрема тимчасова БД для кожного тесту з тестовими даними з seed_data."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import seed_data  # noqa: E402
from app import create_app  # noqa: E402
from models import query_one  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    application = create_app({
        'TESTING': True,
        'DATABASE': str(tmp_path / 'test.sqlite'),
        'CSRF_DISABLED': True,          # CSRF перевіряється окремо в test_security.py
        'ADMIN_PASSWORD': 'test-pass',
        'SECRET_KEY': 'test',
    })
    with application.app_context():
        seed_data.seed()
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin(client):
    response = client.post('/admin/login', data={'password': 'test-pass'})
    assert response.status_code == 302
    return client


@pytest.fixture()
def db_row(app):
    """Виконати SELECT і отримати один рядок (у контексті застосунку)."""
    def run(sql, params=()):
        with app.app_context():
            row = query_one(sql, params)
            return dict(row) if row else None
    return run


def product_id(db_row, slug):
    return db_row('SELECT id FROM products WHERE slug = ?', (slug,))['id']
