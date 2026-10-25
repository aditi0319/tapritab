# ☕ TapriTab

![CI](https://github.com/aditi0319/tapritab/actions/workflows/ci.yml/badge.svg)

**Live demo:** https://tapritab.onrender.com
*(Free hosting: the first visit after a while can take about a minute to wake up.)*

TapriTab is a Django web app for tracking shared expenses in friend groups, like the daily chai and snack run. Create a group, invite friends with a link, log who paid for what, and settle up with the fewest possible payments and one-tap UPI links.

> *Chai pe charcha, hisaab pe nahi.*

## Features

- **Groups and invite links:** create a group and share a secure UUID invite link (also on WhatsApp). Admins can reset the link or remove members.
- **Expenses with 3 split types:** equal, exact amounts or percentages, with an optional bill photo.
- **Paisa-accurate splitting:** money is stored as `Decimal`, and splits use the largest-remainder method so shares always add up exactly (₹100 ÷ 3 = 33.34 + 33.33 + 33.33).
- **Balances and Settle Up:** a greedy debt-simplification algorithm suggests at most *n − 1* payments for *n* people, with UPI deep links (`upi://pay?...`).
- **Payment confirmation:** payments recorded by the payer stay pending until the receiver confirms.
- **Dashboard:** total owed and owing across groups, recent activity and pending confirmations.
- **⚡ Quick Add:** "Chai for everyone, ₹15 each" in one tap.
- **👑 Chai King:** a monthly leaderboard of who bought the most chai.
- **REST API:** Django REST Framework endpoints for groups, expenses and balances.

## Tech stack

| Area | Tools |
| --- | --- |
| Backend | Python 3.13, Django 6, Django REST Framework |
| Database | PostgreSQL (production, CI), SQLite (local) |
| Frontend | Django templates, Bootstrap 5, a little JavaScript |
| Testing | Django `TestCase`, DRF `APITestCase` (37 tests) |
| CI/CD | GitHub Actions (tests on PostgreSQL), Render auto-deploy after checks pass |
| Production | Gunicorn, WhiteNoise, HTTPS-only secure cookies, environment-based config |

## Design decisions

- **Business logic in a service layer** (`expenses/services.py`), shared by the website and the API, and unit-tested on its own.
- **Database transactions** (`transaction.atomic`) so an expense and all its splits are saved together or not at all.
- **Database constraints:** one membership per user per group, one split per person per expense, and no paying yourself (`CheckConstraint`).
- **Query optimisation** with `select_related`, `prefetch_related` and database-side `annotate`/`Sum`, avoiding N+1 queries.
- **Security:** every group view checks membership (non-members get a 404), state-changing actions are POST-only with CSRF protection, and admin actions are checked on the server.

## API endpoints

| Method | URL | Description |
| --- | --- | --- |
| GET | `/api/groups/` | Your groups, with member count and your balance |
| GET | `/api/groups/<id>/` | One group with its members |
| GET, POST | `/api/groups/<id>/expenses/` | List or add expenses |
| GET | `/api/groups/<id>/balances/` | Balances and suggested payments |

All endpoints require login and only return groups you belong to.

## Run it locally

```bash
git clone https://github.com/aditi0319/tapritab.git
cd tapritab
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env         # Mac/Linux: cp .env.example .env, then add a SECRET_KEY
python manage.py migrate
python manage.py runserver
```

Run the tests:

```bash
python manage.py test
```

## Project structure

```
accounts/   registration, login, profile with UPI ID (auto-created by a signal)
groups/     groups, memberships, invite links, dashboard
expenses/   expenses, splits, settlements, balance and settle-up logic
api/        Django REST Framework serializers, views and URLs
templates/  Django templates (Bootstrap 5)
.github/    GitHub Actions CI workflow
render.yaml Render deployment blueprint (infrastructure as code)
```

## Roadmap

- Store uploaded photos on AWS S3 (the free host's disk is temporary)
- Token authentication for a mobile app
- Cache balances for very large groups
