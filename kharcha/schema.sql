-- Reference schema (SQLite). The app creates these tables itself through the
-- SQLAlchemy models; this file documents the design and lets you explore in any SQL client.

PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    name          VARCHAR(80)  NOT NULL,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL
);

CREATE TABLE categories (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER     NOT NULL REFERENCES users(id),
    name    VARCHAR(40) NOT NULL,
    CONSTRAINT uq_category_user_name UNIQUE (user_id, name)
);

-- Money is stored as integer paise (₹1 = 100 paise) to avoid floating-point errors.
CREATE TABLE expenses (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER      NOT NULL REFERENCES users(id),
    category_id  INTEGER      NOT NULL REFERENCES categories(id),
    description  VARCHAR(200) NOT NULL,
    amount_paise INTEGER      NOT NULL,
    spent_on     DATE         NOT NULL,
    created_at   DATETIME     NOT NULL,
    CONSTRAINT ck_expense_amount_positive CHECK (amount_paise > 0)
);
CREATE INDEX ix_expenses_user_date ON expenses (user_id, spent_on);

CREATE TABLE budgets (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    month       VARCHAR(7) NOT NULL,          -- 'YYYY-MM'
    limit_paise INTEGER NOT NULL,
    CONSTRAINT uq_budget_user_cat_month UNIQUE (user_id, category_id, month),
    CONSTRAINT ck_budget_limit_positive CHECK (limit_paise > 0)
);

-- ---------------------------------------------------------------
-- Practice queries (replace 1 with a real user id)
-- ---------------------------------------------------------------

-- 1. Spend per category for one month, biggest first
SELECT c.name, SUM(e.amount_paise) / 100.0 AS rupees, COUNT(*) AS n
FROM expenses e JOIN categories c ON c.id = e.category_id
WHERE e.user_id = 1 AND e.spent_on >= '2026-09-01' AND e.spent_on < '2026-10-01'
GROUP BY c.id, c.name
ORDER BY rupees DESC;

-- 2. Categories that went over budget (JOIN + subquery + HAVING-style filter)
SELECT c.name, b.limit_paise, s.spent
FROM budgets b
JOIN categories c ON c.id = b.category_id
JOIN (SELECT category_id, SUM(amount_paise) AS spent
      FROM expenses
      WHERE user_id = 1 AND spent_on >= '2026-09-01' AND spent_on < '2026-10-01'
      GROUP BY category_id) s ON s.category_id = b.category_id
WHERE b.user_id = 1 AND b.month = '2026-09' AND s.spent > b.limit_paise;

-- 3. Days with above-average spending (window-free version using a subquery)
SELECT spent_on, SUM(amount_paise) AS day_total
FROM expenses WHERE user_id = 1
GROUP BY spent_on
HAVING day_total > (SELECT AVG(d) FROM (SELECT SUM(amount_paise) AS d FROM expenses WHERE user_id = 1 GROUP BY spent_on))
ORDER BY day_total DESC;

-- 4. Categories with no expenses this month (LEFT JOIN + IS NULL)
SELECT c.name
FROM categories c
LEFT JOIN expenses e ON e.category_id = c.id AND e.spent_on >= '2026-09-01' AND e.spent_on < '2026-10-01'
WHERE c.user_id = 1 AND e.id IS NULL;
