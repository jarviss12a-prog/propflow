"""SQLite access and schema migrations.

Migrations are applied in order using PRAGMA user_version. To change the
schema, APPEND a new SQL string to MIGRATIONS — never edit an old one, or
existing databases on the VPS won't pick up the change.
"""
import sqlite3

from flask import current_app, g

MIGRATIONS = [
    # 1 — initial schema
    """
    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE properties (
        id                   INTEGER PRIMARY KEY,
        name                 TEXT NOT NULL,
        address              TEXT NOT NULL DEFAULT '',
        city                 TEXT NOT NULL DEFAULT '',
        state                TEXT NOT NULL DEFAULT 'IN',
        zip                  TEXT NOT NULL DEFAULT '',
        property_type        TEXT NOT NULL DEFAULT 'single_family',
        owner_entity         TEXT NOT NULL DEFAULT '',
        purchase_date        TEXT,
        purchase_price_cents INTEGER,
        land_value_cents     INTEGER,
        placed_in_service    TEXT,
        mortgage_lender      TEXT NOT NULL DEFAULT '',
        notes                TEXT NOT NULL DEFAULT '',
        archived             INTEGER NOT NULL DEFAULT 0,
        created_at           TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE units (
        id                INTEGER PRIMARY KEY,
        property_id       INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
        label             TEXT NOT NULL DEFAULT 'Main',
        beds              REAL,
        baths             REAL,
        sqft              INTEGER,
        market_rent_cents INTEGER,
        notes             TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE tenants (
        id         INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        phone      TEXT NOT NULL DEFAULT '',
        email      TEXT NOT NULL DEFAULT '',
        notes      TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- A lease ties a tenant to a unit. end_date is the lease term (NULL = month to month).
    -- move_out_date is when they actually left; only that stops rent being expected.
    CREATE TABLE leases (
        id                    INTEGER PRIMARY KEY,
        unit_id               INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
        tenant_id             INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        start_date            TEXT NOT NULL,
        end_date              TEXT,
        move_out_date         TEXT,
        rent_cents            INTEGER NOT NULL,
        due_day               INTEGER NOT NULL DEFAULT 1,
        grace_days            INTEGER NOT NULL DEFAULT 5,
        late_fee_cents        INTEGER NOT NULL DEFAULT 0,
        deposit_cents         INTEGER NOT NULL DEFAULT 0,
        section8              INTEGER NOT NULL DEFAULT 0,
        hap_cents             INTEGER NOT NULL DEFAULT 0,
        housing_authority     TEXT NOT NULL DEFAULT '',
        s8_case_number        TEXT NOT NULL DEFAULT '',
        ledger_start          TEXT NOT NULL,
        opening_balance_cents INTEGER NOT NULL DEFAULT 0,
        notes                 TEXT NOT NULL DEFAULT '',
        created_at            TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE contacts (
        id         INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        company    TEXT NOT NULL DEFAULT '',
        role       TEXT NOT NULL DEFAULT 'Other',
        phone      TEXT NOT NULL DEFAULT '',
        email      TEXT NOT NULL DEFAULT '',
        notes      TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE maintenance (
        id            INTEGER PRIMARY KEY,
        property_id   INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
        unit_id       INTEGER REFERENCES units(id) ON DELETE SET NULL,
        tenant_id     INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
        contact_id    INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
        title         TEXT NOT NULL,
        details       TEXT NOT NULL DEFAULT '',
        status        TEXT NOT NULL DEFAULT 'open',
        urgent        INTEGER NOT NULL DEFAULT 0,
        opened_on     TEXT NOT NULL,
        scheduled_for TEXT,
        closed_on     TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Money in. property_id is always set so income is never lost if a lease is deleted.
    CREATE TABLE payments (
        id           INTEGER PRIMARY KEY,
        date         TEXT NOT NULL,
        property_id  INTEGER NOT NULL REFERENCES properties(id) ON DELETE RESTRICT,
        lease_id     INTEGER REFERENCES leases(id) ON DELETE SET NULL,
        kind         TEXT NOT NULL DEFAULT 'rent',
        amount_cents INTEGER NOT NULL,
        applies_to   TEXT,
        method       TEXT NOT NULL DEFAULT '',
        reference    TEXT NOT NULL DEFAULT '',
        notes        TEXT NOT NULL DEFAULT '',
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Money out. property_id NULL = shared across the portfolio (split at tax time).
    CREATE TABLE expenses (
        id             INTEGER PRIMARY KEY,
        date           TEXT NOT NULL,
        property_id    INTEGER REFERENCES properties(id) ON DELETE RESTRICT,
        category       TEXT NOT NULL,
        vendor         TEXT NOT NULL DEFAULT '',
        contact_id     INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
        maintenance_id INTEGER REFERENCES maintenance(id) ON DELETE SET NULL,
        amount_cents   INTEGER NOT NULL,
        method         TEXT NOT NULL DEFAULT '',
        reference      TEXT NOT NULL DEFAULT '',
        notes          TEXT NOT NULL DEFAULT '',
        created_at     TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE files (
        id            INTEGER PRIMARY KEY,
        entity_type   TEXT NOT NULL,
        entity_id     INTEGER NOT NULL,
        original_name TEXT NOT NULL,
        stored_name   TEXT NOT NULL UNIQUE,
        size          INTEGER NOT NULL,
        content_type  TEXT NOT NULL DEFAULT '',
        uploaded_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX idx_units_property ON units(property_id);
    CREATE INDEX idx_leases_unit ON leases(unit_id);
    CREATE INDEX idx_leases_tenant ON leases(tenant_id);
    CREATE INDEX idx_payments_date ON payments(date);
    CREATE INDEX idx_payments_lease ON payments(lease_id, applies_to);
    CREATE INDEX idx_payments_property ON payments(property_id);
    CREATE INDEX idx_expenses_date ON expenses(date);
    CREATE INDEX idx_expenses_property ON expenses(property_id);
    CREATE INDEX idx_maintenance_status ON maintenance(status);
    CREATE INDEX idx_files_entity ON files(entity_type, entity_id);
    """,
]


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def migrate(conn):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {i};\nCOMMIT;")
    return conn.execute("PRAGMA user_version").fetchone()[0]


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def scalar(sql, args=()):
    row = get_db().execute(sql, args).fetchone()
    return row[0] if row else None


def execute(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    return cur.lastrowid


def get_setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key = ?", (key,), one=True)
    return row["value"] if row else default


def set_setting(key, value):
    execute("INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def init_app(app):
    app.teardown_appcontext(close_db)
    conn = connect(app.config["DATABASE"])
    try:
        migrate(conn)
    finally:
        conn.close()
