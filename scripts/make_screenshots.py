"""Знімає скриншоти для звіту (lab-reports/screenshots).

Запуск: python scripts/make_screenshots.py
Застосунок запускається на тимчасовій БД з тестовими даними (seed_data), робоча db.sqlite не змінюється.
Потрібні: pip install playwright (браузер — вбудований Chromium або встановлений Chrome).
"""
import html
import os
import sqlite3
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import seed_data  # noqa: E402
from app import create_app  # noqa: E402

OUT = os.path.join(ROOT, 'lab-reports', 'screenshots')
PASSWORD = 'admin123'
DESKTOP = {'width': 1440, 'height': 900}
MOBILE = {'width': 390, 'height': 844}


def launch(playwright):
    try:
        return playwright.chromium.launch()
    except Exception:
        return playwright.chromium.launch(channel='chrome')


def shot(page, name, full=True):
    page.screenshot(path=os.path.join(OUT, f'{name}.png'), full_page=full)
    print('✓', name)


def schema_html(db_path):
    """HTML-картки таблиць зі стовпцями, PK і FK — читається з PRAGMA реальної БД."""
    con = sqlite3.connect(db_path)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    cards = []
    for table in tables:
        fks = {row[3]: (row[2], row[4], row[6]) for row in con.execute(f'PRAGMA foreign_key_list({table})')}
        rows = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        lines = []
        for _, name, col_type, notnull, _, pk in con.execute(f'PRAGMA table_info({table})'):
            if pk:
                mark = '🔑 PK'
            elif name in fks:
                mark = f'🔗 FK → {fks[name][0]}.{fks[name][1]} ({fks[name][2]})'
            else:
                mark = ''
            lines.append(f'<tr><td><b>{name}</b></td><td>{col_type}{" NOT NULL" if notnull else ""}</td>'
                         f'<td class="k">{html.escape(mark)}</td></tr>')
        cards.append(f'<section><h2>{table} <small>{rows} рядків</small></h2><table>{"".join(lines)}</table></section>')
    con.close()
    return ('<html><head><meta charset="utf-8"><style>body{font:14px "Segoe UI",sans-serif;background:#f6f3ee;margin:24px}'
            'h1{margin:0 0 16px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;align-items:start}'
            'section{background:#fff;border:1px solid #e2dacd;border-radius:14px;padding:14px 16px}'
            'h2{margin:0 0 8px;font-size:17px;color:#d9480f}small{color:#6b6258;font-weight:400}'
            'table{border-collapse:collapse;width:100%}td{padding:3px 6px;border-top:1px solid #f1ece4}td:nth-child(2){white-space:nowrap}'
            '.k{color:#7048e8;font-size:12px}</style></head><body>'
            '<h1>Схема бази даних db.sqlite (PRAGMA table_info / foreign_key_list)</h1>'
            f'<main>{"".join(cards)}</main></body></html>')


def shop_flow(page, base):
    for name, path in [('home', '/'), ('catalog', '/catalog'),
                       ('catalog-filters', '/catalog?category=strategy&max_price=2700&players=4&sort=price_asc'),
                       ('catalog-search', '/catalog?q=марс'), ('product', '/catalog/carcassonne'),
                       ('feedback', '/feedback'), ('404', '/catalog/xyz')]:
        page.goto(base + path)
        shot(page, f'{name}-desktop')

    page.goto(base + '/feedback')
    page.fill('#f-name', 'А')
    page.fill('#f-email', 'не-email')
    page.click('form.form-card button[type=submit]')
    shot(page, 'feedback-errors-desktop')

    page.goto(base + '/catalog/carcassonne')
    page.fill('#qty', '2')
    page.click('.buy-form button')
    page.goto(base + '/catalog/codenames')
    page.click('.buy-form button')
    page.fill('#promo', 'PARTY15')
    page.click('.promo-form button')
    shot(page, 'cart-promo-desktop')

    page.goto(base + '/checkout')
    page.click('form.form-card button[type=submit]')
    shot(page, 'checkout-errors-desktop')
    for field, value in [('name', 'Ілля Пламетюк'), ('phone', '+380 67 123 45 67'), ('email', 'student@example.com'),
                         ('city', 'Луцьк'), ('address', 'Відділення Нової пошти №3'), ('comment', 'Подарункове пакування')]:
        page.fill(f'#f-{field}', value)
    page.click('form.form-card button[type=submit]')
    shot(page, 'order-success-desktop')


def admin_flow(page, base):
    page.on('dialog', lambda dialog: dialog.accept())   # підтвердження confirm() для видалення
    page.goto(base + '/admin/')
    shot(page, 'admin-login-desktop')
    page.fill('#password', PASSWORD)
    page.click('.login-card button')
    for name, path in [('dashboard', '/admin/'), ('orders', '/admin/orders'), ('order-detail', '/admin/orders/7'),
                       ('products', '/admin/products'), ('categories', '/admin/categories'),
                       ('customers', '/admin/customers'), ('customer-detail', '/admin/customers/1'),
                       ('promos', '/admin/promos'), ('feedback', '/admin/feedback')]:
        page.goto(base + path)
        shot(page, f'admin-{name}-desktop')

    page.goto(base + '/admin/orders/7')
    page.select_option('#status', 'Підтверджене')
    page.click('.inline-form button')
    shot(page, 'admin-order-status-desktop')

    page.goto(base + '/admin/products/new')
    page.fill('#f-name', 'X')
    page.fill('#f-slug', 'Погана Адреса')
    page.fill('#f-price', '-10')
    page.fill('#f-players_min', '6')
    page.fill('#f-players_max', '2')
    page.click('.form-actions button')
    shot(page, 'admin-product-errors-desktop')

    page.goto(base + '/admin/products')
    page.locator('tr', has_text='Каркасон').locator('button.btn-danger-ghost').click()
    page.wait_for_load_state()
    shot(page, 'admin-delete-restricted-desktop', full=False)


def mobile_flow(page, base):
    for name, path in [('home', '/'), ('catalog', '/catalog'), ('cart', '/cart')]:
        page.goto(base + path)
        shot(page, f'{name}-mobile', full=False)
    page.goto(base + '/admin/login')
    page.fill('#password', PASSWORD)
    page.click('.login-card button')
    shot(page, 'admin-dashboard-mobile', full=False)


def main():
    os.makedirs(OUT, exist_ok=True)
    db_path = os.path.join(tempfile.mkdtemp(), 'screens.sqlite')
    app = create_app({'DATABASE': db_path, 'ADMIN_PASSWORD': PASSWORD})
    with app.app_context():
        seed_data.seed()
    server = make_server('127.0.0.1', 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'

    with sync_playwright() as p:
        browser = launch(p)
        shop_flow(browser.new_page(viewport=DESKTOP), base)
        admin_flow(browser.new_page(viewport=DESKTOP), base)
        mobile = browser.new_page(viewport=MOBILE, device_scale_factor=2)
        mobile.goto(base + '/catalog/dobble')
        mobile.click('.buy-form button')
        mobile_flow(mobile, base)

        schema = browser.new_page(viewport={'width': 1440, 'height': 900})
        schema.set_content(schema_html(db_path))
        shot(schema, 'db-schema')
        browser.close()
    server.shutdown()


if __name__ == '__main__':
    main()
