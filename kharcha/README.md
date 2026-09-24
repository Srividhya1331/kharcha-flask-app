# Kharcha — Personal Expense Tracker

A full-stack expense tracker built with **Python, Flask, SQL (SQLite via SQLAlchemy) and Git**.
Log expenses in ₹, organise them by category, set monthly budgets, and see where your money goes.

| Skill in the job listing | Where it shows up in this project |
|---|---|
| Python | Service layer, validation, pure helper functions, Click CLI command |
| Flask | App factory, blueprints, Flask-Login auth, error handlers, Jinja templates |
| SQL | Hand-written analytics in `reports.py` (JOIN, GROUP BY, subquery, LEFT JOIN, COALESCE), schema constraints and indexes in `schema.sql` |
| Git | Branch-per-feature workflow below, `.gitignore`, conventional commit messages |
| Problem-solving | See "Problems this project solves" below |

## Features
- Register / log in / log out (hashed passwords, per-user data)
- Add, edit, delete expenses; search, filter by month and category; pagination
- Dashboard: month total vs last month, category breakdown, 6-month trend, latest expenses
- Monthly budgets per category with ok / warning (80%+) / over-budget states
- CSV export of the current filter
- JSON API: `GET /api/expenses`, `POST /api/expenses`, `GET /api/summary`
- 48 automated tests (pytest)

## Run it
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

flask --app expense_tracker seed-demo   # optional: demo@example.com / demo12345 with 6 months of data
flask --app expense_tracker run --debug # http://127.0.0.1:5000
pytest                                  # run the tests
```
Set `SECRET_KEY` (and optionally `DATABASE_URL`) as environment variables outside development.

## Project layout
```
expense_tracker/
  __init__.py   app factory, CSRF check, error handlers, seed-demo command
  models.py     User, Category, Expense, Budget
  auth.py       register / login / logout
  main.py       dashboard, expenses CRUD, CSV export, budgets
  api.py        JSON endpoints
  services.py   validation + query building shared by HTML and API
  reports.py    raw-SQL analytics
  utils.py      money, month and security helpers
  templates/  static/
tests/          unit, route, SQL-report, API and security tests
schema.sql      DDL + practice queries
```

## Problems this project solves (good interview material)
1. **Floating-point money.** `0.1 + 0.2 != 0.3`. Amounts are stored as integer paise and parsed with `Decimal`, so totals are always exact.
2. **Broken charts from missing months.** A plain `GROUP BY` skips months with no spending. `monthly_trend()` fills gaps with zero, and month arithmetic handles the December → January rollover.
3. **Slow date queries.** Filtering with `strftime()` on a column bypasses the index. Queries use a half-open range (`>= start AND < end`) on the `(user_id, spent_on)` index.
4. **N+1 queries.** The expense list uses `joinedload` so 10 rows cost 1 query, not 11.
5. **Users seeing each other's data.** Every query filters by `user_id`; another user's expense id returns 404, not 403, so ids can't be probed. Category ids submitted in forms are checked for ownership too.
6. **Security basics.** CSRF tokens on every POST, open-redirect check on `?next=`, identical login error for wrong email or password, CSV formula-injection guard, `LIKE` wildcards escaped in search.
7. **All-or-nothing budget saves.** If one field is invalid nothing is written, so the user never ends up with half-saved data.

## Git workflow to use while building it
```bash
git init && git add . && git commit -m "chore: initial Flask project skeleton"
git checkout -b feature/expenses-crud
# ...work...
git commit -m "feat: add expense create/edit/delete with validation"
git checkout main && git merge --no-ff feature/expenses-crud
```
Suggested branch/commit order: `models` → `auth` → `expenses-crud` → `reports-sql` → `budgets` → `api` → `tests` → `csv-export`.
Use prefixes `feat:`, `fix:`, `test:`, `docs:`, `refactor:`. Small, focused commits read much better than one big one.

## Ideas to extend it
- Custom categories (add / rename / archive)
- Recurring expenses (monthly rent, subscriptions)
- Switch to PostgreSQL (`DATABASE_URL=postgresql://...`) and replace `strftime` with `to_char`
- Alembic migrations, Docker file, deploy on Render or Railway
- Charts with Chart.js; token-based API auth
