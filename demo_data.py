"""Made-up sample data for trying the app (python manage.py demo). Refuses to run on a database with data."""
from datetime import date

from app.db import get_db
from app.utils import add_months, local_today, ym_of

PROPS = [
    ("Birch Ln", "1 Birch Ln", "Merrillville", 1, "2018-05-10", 92_000, 15_000, "Example Bank"),
    ("Cedar Duplex", "22 Cedar Ct", "Hobart", 2, "2020-09-01", 148_000, 22_000, "Example Credit Union"),
    ("Willow St", "3 Willow St", "Portage", 1, "2021-02-15", 110_000, 18_000, "Example Bank"),
    ("Aspen Ave", "4 Aspen Ave", "Valparaiso", 1, "2022-07-20", 135_000, 25_000, ""),
]
TENANTS = [  # property idx, unit idx, name, rent, hap, start, late_months
    (0, 0, "Sample Tenant A", 1150, 0, "2023-06-01", []),
    (1, 0, "Sample Tenant B", 975, 780, "2022-01-01", []),
    (1, 1, "Sample Tenant C", 950, 0, "2024-03-01", [0]),
    (2, 0, "Sample Tenant D", 1295, 0, "2025-08-01", []),
    (3, 0, "Sample Tenant E", 1400, 1050, "2024-10-01", [0]),
]


def load():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM properties").fetchone()[0]:
        raise SystemExit("Database already has data; demo only loads into an empty one.")
    today = local_today()
    year_start = f"{today.year}-01"
    pids, units = [], []
    for name, addr, city, n, bought, price, land, lender in PROPS:
        pid = db.execute("""INSERT INTO properties (name, address, city, state, zip, property_type, owner_entity,
                            purchase_date, purchase_price_cents, land_value_cents, mortgage_lender)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         (name, addr, city, "IN", "46000", "duplex" if n == 2 else "single_family", "Example LLC",
                          bought, price * 100, land * 100, lender)).lastrowid
        pids.append(pid)
        labels = ["Main"] if n == 1 else ["Unit A", "Unit B"]
        units.append([db.execute("INSERT INTO units (property_id, label) VALUES (?,?)", (pid, lb)).lastrowid
                      for lb in labels])
    cur = ym_of(today)
    for pi, ui, name, rent, hap, start, late in TENANTS:
        tid = db.execute("INSERT INTO tenants (name, phone) VALUES (?, ?)", (name, "555-0100")).lastrowid
        lid = db.execute("""INSERT INTO leases (unit_id, tenant_id, start_date, end_date, rent_cents, deposit_cents,
                            section8, hap_cents, housing_authority, ledger_start, late_fee_cents)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                         (units[pi][ui], tid, start, None if hap else f"{today.year + (1 if pi % 2 else 0)}-0{1 + pi}-28",
                          rent * 100, rent * 100, 1 if hap else 0, hap * 100,
                          "Example Housing Authority" if hap else "", year_start, 5000)).lastrowid
        m = year_start
        while m <= cur:
            back = (int(cur[:4]) * 12 + int(cur[5:])) - (int(m[:4]) * 12 + int(m[5:]))
            if back in late:
                m = add_months(m, 1)
                continue
            y, mo = int(m[:4]), int(m[5:])
            if hap:
                db.execute("INSERT INTO payments (date, property_id, lease_id, kind, amount_cents, applies_to, method) "
                           "VALUES (?,?,?,?,?,?,?)", (date(y, mo, 1).isoformat(), pids[pi], lid, "hap", hap * 100, m,
                                                      "Housing authority"))
            if not (back == 0 and today.day < 4):
                db.execute("INSERT INTO payments (date, property_id, lease_id, kind, amount_cents, applies_to, method) "
                           "VALUES (?,?,?,?,?,?,?)", (date(y, mo, min(3 + pi, 28)).isoformat(), pids[pi], lid, "rent",
                                                      (rent - hap) * 100, m, "Zelle" if pi % 2 else "Check"))
            m = add_months(m, 1)
    exp = [
        (0, "repairs", "Example Plumbing", 18500, "-03-14"), (1, "repairs", "Example HVAC", 64000, "-01-22"),
        (2, "cleaning_maintenance", "Example Lawn Co", 4500, "-06-02"), (2, "cleaning_maintenance", "Example Lawn Co", 4500, "-07-02"),
        (None, "legal_professional", "Example CPA", 45000, "-03-01"), (None, "insurance", "Example Umbrella Policy", 38000, "-02-10"),
        (3, "taxes", "County Treasurer", 112000, "-05-10"), (1, "taxes", "County Treasurer", 98000, "-05-10"),
        (0, "utilities", "City Water", 6200, "-04-20"), (3, "capital_improvement", "Example Roofing", 850000, "-08-15"),
        (2, "supplies", "Hardware store", 3870, "-09-03"),
    ]
    for pi, cat, vendor, cents, md in exp:
        d = f"{today.year}{md}"
        if d <= today.isoformat():
            db.execute("INSERT INTO expenses (date, property_id, category, vendor, amount_cents, method) VALUES (?,?,?,?,?,?)",
                       (d, pids[pi] if pi is not None else None, cat, vendor, cents, "Card"))
    m = year_start
    while m <= cur:
        for pi, (i, p) in [(0, (41000, 39000)), (1, (52000, 46000))]:
            d = f"{m}-01"
            for cat, cents in (("mortgage_interest", i), ("mortgage_principal", p)):
                db.execute("INSERT INTO expenses (date, property_id, category, vendor, amount_cents, notes) "
                           "VALUES (?,?,?,?,?,?)", (d, pids[pi], cat, PROPS[pi][7], cents, "Mortgage payment"))
        m = add_months(m, 1)
    db.execute("INSERT INTO contacts (name, role, phone) VALUES ('Example Plumbing', 'Plumber', '555-0111')")
    db.execute("INSERT INTO contacts (name, role, phone) VALUES ('Example Housing Authority', 'Housing authority', '555-0122')")
    db.execute("INSERT INTO maintenance (property_id, title, status, urgent, opened_on) VALUES (?,?,?,?,?)",
               (pids[1], "Furnace short-cycling, Unit A", "open", 1, today.isoformat()))
    db.execute("INSERT INTO maintenance (property_id, title, status, opened_on, scheduled_for) VALUES (?,?,?,?,?)",
               (pids[3], "Gutter cleaning", "scheduled", today.isoformat(), today.isoformat()))
    db.commit()
