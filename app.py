"""Магазин настільних ігор «Кубик» — лабораторна робота 04 (Flask + SQLite).

Запуск:
    python seed_data.py   # тестові дані (необов'язково)
    python app.py         # http://127.0.0.1:5000, адмін-панель: /admin
"""
import os
from datetime import datetime

from flask import Flask, render_template, session

import content
import models
from models.orders import STATUS_COLORS
from routes import admin_bp, feedback_bp, main_bp, shop_bp
from security import check_csrf, csrf_token

NAV_ITEMS = [
    ('main.home', 'Головна'),
    ('shop.catalog', 'Каталог'),
    ('main.about', 'Про нас'),
    ('main.delivery', 'Доставка й оплата'),
    ('feedback.feedback', 'Відгуки'),
    ('main.contacts', 'Контакти'),
]


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get('DATABASE', os.path.join(app.root_path, 'db.sqlite')),
        # Ключ підписує cookie сесії (кошик, вхід адміністратора).
        # Для реального сайту задайте SECRET_KEY і ADMIN_PASSWORD у змінних середовища.
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-only-change-me'),
        ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD', 'admin123'),
    )
    if config:
        app.config.update(config)

    app.teardown_appcontext(models.close_db)
    with app.app_context():
        models.init_db()

    app.before_request(check_csrf)
    for blueprint in (main_bp, shop_bp, feedback_bp, admin_bp):
        app.register_blueprint(blueprint)

    register_template_helpers(app)
    register_error_pages(app)
    return app


def register_template_helpers(app):
    @app.context_processor
    def inject_globals():
        cart = session.get('cart', {})
        return {
            'shop': content.SHOP,
            'nav_items': NAV_ITEMS,
            'current_year': datetime.now().year,
            'cart_count': sum(cart.values()),
            'csrf_token': csrf_token,
            'status_colors': STATUS_COLORS,
        }

    @app.template_filter('price')
    def format_price(value):
        """1150 -> '1 150 грн'; копійки показуються лише якщо вони є."""
        value = float(value or 0)
        text = f'{value:,.2f}' if value % 1 else f'{value:,.0f}'
        return text.replace(',', ' ') + ' грн'

    @app.template_filter('players')
    def format_players(product):
        low, high = product['players_min'], product['players_max']
        return str(low) if low == high else f'{low}–{high}'


def register_error_pages(app):
    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    def error_page(error):
        return render_template('error.html', error=error), error.code


if __name__ == '__main__':
    create_app().run(debug=True)
