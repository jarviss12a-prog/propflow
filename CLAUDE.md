# PropFlow: notes for Claude Code

Private rental tracker for Adrian's Indiana rental properties. Owner-only dashboard (no tenant logins yet). Runs on his VPS behind Tailscale; he uses it mostly from his phone. Main goal: make tax time easy, so every dollar must land on the right Schedule E line.

## Stack

- Flask 3, SQLite (raw `sqlite3`, no ORM), Jinja templates, one stylesheet (`app/static/style.css`), tiny optional `app/static/app.js`. No build step, no npm.
- Gunicorn on 127.0.0.1, exposed with `tailscale serve`. See `deploy/setup.sh`.
- Python 3.9+ compatible.

## Layout

```
app/__init__.py      create_app(), blueprint registration, error pages
app/db.py            connection helpers + MIGRATIONS list (PRAGMA user_version)
app/constants.py     Schedule E categories + line numbers, payment kinds, aliases
app/ledger.py        ALL money logic: rent roll, balances, yearly totals, schedule_e()
app/importer.py      CSV import (shared by web Import page and manage.py import)
app/auth.py          single-owner login, CSRF, lockout
app/views/*.py       one blueprint per area: main, properties, tenants, money, reports, crm, files, imports
app/templates/       base.html (nav), _macros.html (form fields, stamp, files block)
manage.py            set-password | import | backup | demo | check
deploy/              setup.sh (first install), update.sh
tests/test_app.py    pytest; run before every commit
```

## Rules

- **Never commit data.** `data/`, `*.db*`, `.env`, `*.csv` are gitignored. The repo has been public before; an old commit leaked a WAL file. Don't add fixtures with real tenant names or amounts.
- **Money is integer cents** everywhere (`*_cents` columns). Parse with `utils.parse_money`, display with the `money` / `money0` filters. Never use floats for money.
- **Schema changes: append a new SQL string to `db.MIGRATIONS`.** Never edit an existing migration. The VPS database upgrades on next start.
- **Totals come from `ledger.py`.** Views and exports call it; don't re-implement sums in a view or template.
- Schedule E mapping lives in `constants.EXPENSE_CATEGORIES` (`line: None` = tracked but not deductible). Income kinds in `PAYMENT_KINDS` (`income: False` for security deposits).
- Rent roll semantics: a lease expects rent each month from `max(start month, ledger_start)` through the `move_out_date` month. `end_date` is informational (holdover = month to month). Rent/HAP payments match a month via `applies_to` (YYYY-MM).
- Every POST form includes `{{ csrf() }}`. Every page except login/setup/health requires login (handled in `auth.guard`).
- Uploads go through `storage.save_upload` (extension allowlist, random stored names) and are served only by `files.download`.

## UI conventions

- Mobile first. Bottom tab bar on phones, sidebar at 900px+. Test at iPhone width.
- Ledger-paper palette defined as CSS variables on `:root` with a dark-mode override; use the variables, not hex values.
- Lists are `.sheet > ul.rows > li > .row` (title, sub, amt, amt-sub). Forms use the macros in `_macros.html` and end with a sticky `.form-foot`.
- Plain, specific copy in sentence case. Buttons say what they do ("Record payment", "Log expense").
- The rubber-stamp status (`stamp()` macro) is the one decorative flourish. Keep everything else quiet.

## When Adrian sends numbers

Turn them into CSVs that match `importer.KINDS` column names (templates: `/import/template/<kind>.csv`). Order: properties → tenants → payments → expenses. Use exact tenant and property names as they appear in PropFlow. He uploads them on the Import page (or runs `manage.py import` on the VPS). Ask about anything ambiguous, like whether a payment is a deposit or rent, rather than guessing, since it changes taxable income.

## Commands

```bash
python -m pytest -q
python manage.py demo     # sample data into an EMPTY ./data
python wsgi.py            # dev server on 127.0.0.1:8050
```

## Not built yet (ideas he mentioned)

- Tenant-facing app: online rent payments (would need Stripe ACH + tenant logins) and maintenance requests from tenants. Deliberately shelved.
- Mileage log for auto/travel deductions.
- Moving properties into a single LLC: `owner_entity` field exists for this.
