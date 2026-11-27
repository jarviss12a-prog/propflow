"""The money logic: rent roll, tenant balances, yearly totals, Schedule E.

Everything here reads the database and returns plain dicts, so views and the
CSV export share one source of truth.
"""
from .constants import (CATEGORY_BY_KEY, DEDUCTIBLE_KEYS, EXPENSE_CATEGORIES, INCOME_KINDS,
                        NON_DEDUCTIBLE_KEYS, RENT_KINDS)
from .db import query
from .utils import add_months, local_today, month_first, month_last, months_between, to_date, ym_of

_RENT_IN = ",".join(f"'{k}'" for k in RENT_KINDS)
_INCOME_IN = ",".join(f"'{k}'" for k in INCOME_KINDS)

LEASE_SELECT = """
    SELECT l.*, t.name AS tenant_name, t.phone AS tenant_phone, u.label AS unit_label,
           u.property_id, p.name AS property_name, p.address AS property_address,
           (SELECT COUNT(*) FROM units u2 WHERE u2.property_id = p.id) AS unit_count
    FROM leases l
    JOIN tenants t ON t.id = l.tenant_id
    JOIN units u ON u.id = l.unit_id
    JOIN properties p ON p.id = u.property_id
"""


def place_label(row):
    """'Maple St' or 'Maple St · Unit B' when the property has several units."""
    if row["unit_count"] and row["unit_count"] > 1:
        return f"{row['property_name']}, {row['unit_label']}"
    return row["property_name"]


def leases_active_in(ym, property_id=None):
    sql = LEASE_SELECT + """
        WHERE l.start_date <= ? AND (l.move_out_date IS NULL OR l.move_out_date >= ?)
          AND p.archived = 0
    """
    args = [month_last(ym).isoformat(), month_first(ym).isoformat()]
    if property_id:
        sql += " AND p.id = ?"
        args.append(property_id)
    sql += " ORDER BY p.name, u.label, t.name"
    return query(sql, args)


def lease_is_current(lease, today=None):
    today = today or local_today()
    return to_date(lease["start_date"]) <= today and (
        not lease["move_out_date"] or to_date(lease["move_out_date"]) >= today)


def _received_by_kind(lease_id, ym):
    rows = query(f"""SELECT kind, COALESCE(SUM(amount_cents), 0) AS total FROM payments
                     WHERE lease_id = ? AND applies_to = ? AND kind IN ({_RENT_IN})
                     GROUP BY kind""", (lease_id, ym))
    return {r["kind"]: r["total"] for r in rows}


def rent_status(expected, received, ym, due_day, grace_days, today=None):
    today = today or local_today()
    cur = ym_of(today)
    if expected <= 0:
        return "paid"
    if received >= expected:
        return "paid"
    if ym > cur:
        return "upcoming"
    if received > 0:
        return "partial"
    if ym == cur and today.day <= due_day + grace_days:
        return "due"
    return "late"


def rent_roll(ym, property_id=None, today=None):
    """One row per lease active in the month: what was expected vs received."""
    rows = []
    for l in leases_active_in(ym, property_id):
        got = _received_by_kind(l["id"], ym)
        expected = l["rent_cents"]
        hap_expected = l["hap_cents"] if l["section8"] else 0
        received = sum(got.values())
        rows.append({
            "lease": l,
            "place": place_label(l),
            "expected": expected,
            "tenant_expected": expected - hap_expected,
            "hap_expected": hap_expected,
            "received": received,
            "received_tenant": got.get("rent", 0),
            "received_hap": got.get("hap", 0),
            "short": max(expected - received, 0),
            "status": rent_status(expected, received, ym, l["due_day"], l["grace_days"], today),
        })
    return rows


def rent_roll_summary(rows):
    return {
        "expected": sum(r["expected"] for r in rows),
        "received": sum(min(r["received"], r["expected"]) for r in rows),
        "outstanding": sum(r["short"] for r in rows if r["status"] in ("late", "partial")),
        "late": sum(1 for r in rows if r["status"] == "late"),
        "partial": sum(1 for r in rows if r["status"] == "partial"),
        "paid": sum(1 for r in rows if r["status"] == "paid"),
        "count": len(rows),
    }


def lease_balance(lease, today=None):
    """What the tenant (plus housing authority) owes right now.

    opening balance + rent for every month from ledger_start through the
    current month (once its due day has arrived), minus rent/HAP received for
    those months. Stops at the move-out month. Positive = they owe you.
    """
    today = today or local_today()
    last = ym_of(today)
    if today.day < lease["due_day"]:
        last = add_months(last, -1)
    if lease["move_out_date"]:
        last = min(last, ym_of(lease["move_out_date"]))
    start = max(lease["ledger_start"], ym_of(lease["start_date"]))
    months = months_between(start, last)
    charged = lease["opening_balance_cents"] + lease["rent_cents"] * len(months)
    paid = query(f"""SELECT COALESCE(SUM(amount_cents), 0) AS t FROM payments
                     WHERE lease_id = ? AND kind IN ({_RENT_IN}) AND applies_to >= ?""",
                 (lease["id"], lease["ledger_start"]), one=True)["t"]
    return charged - paid


def lease_months(lease, today=None):
    """Month-by-month ledger for a tenant page, newest first."""
    today = today or local_today()
    last = ym_of(today)
    if lease["move_out_date"]:
        last = min(last, ym_of(lease["move_out_date"]))
    start = max(lease["ledger_start"], ym_of(lease["start_date"]))
    out = []
    for ym in reversed(months_between(start, last)):
        got = _received_by_kind(lease["id"], ym)
        received = sum(got.values())
        out.append({"ym": ym, "expected": lease["rent_cents"], "received": received,
                    "status": rent_status(lease["rent_cents"], received, ym, lease["due_day"],
                                          lease["grace_days"], today)})
    return out


# ---------- yearly totals ----------

def year_bounds(year):
    return f"{year:04d}-01-01", f"{year:04d}-12-31"


def income_total(start, end, property_id=None):
    sql = f"SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE kind IN ({_INCOME_IN}) AND date BETWEEN ? AND ?"
    args = [start, end]
    if property_id:
        sql += " AND property_id = ?"
        args.append(property_id)
    return query(sql, args, one=True)[0]


def expense_total(start, end, property_id=None, deductible_only=True):
    keys = DEDUCTIBLE_KEYS if deductible_only else [c["key"] for c in EXPENSE_CATEGORIES]
    marks = ",".join("?" * len(keys))
    sql = f"SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE category IN ({marks}) AND date BETWEEN ? AND ?"
    args = [*keys, start, end]
    if property_id:
        sql += " AND property_id = ?"
        args.append(property_id)
    return query(sql, args, one=True)[0]


def by_property(start, end):
    """Income, deductible expenses and net per property for a date range."""
    props = query("SELECT id, name FROM properties WHERE archived = 0 ORDER BY name")
    inc = {r[0]: r[1] for r in query(
        f"SELECT property_id, SUM(amount_cents) FROM payments WHERE kind IN ({_INCOME_IN}) "
        "AND date BETWEEN ? AND ? GROUP BY property_id", (start, end))}
    marks = ",".join("?" * len(DEDUCTIBLE_KEYS))
    exp = {r[0]: r[1] for r in query(
        f"SELECT property_id, SUM(amount_cents) FROM expenses WHERE category IN ({marks}) "
        "AND date BETWEEN ? AND ? GROUP BY property_id", (*DEDUCTIBLE_KEYS, start, end))}
    rows = [{"id": p["id"], "name": p["name"], "income": inc.get(p["id"], 0),
             "expenses": exp.get(p["id"], 0)} for p in props]
    for r in rows:
        r["net"] = r["income"] - r["expenses"]
    shared = exp.get(None, 0)
    return rows, shared


# ---------- Schedule E ----------

def depreciation_estimate(prop, year):
    """Straight-line 27.5 years, mid-month convention, on (purchase price − land).

    An estimate only: ignores improvements, prior-owner adjustments and
    closing costs. Your CPA's depreciation schedule wins.
    """
    price, land = prop["purchase_price_cents"], prop["land_value_cents"] or 0
    pis = prop["placed_in_service"] or prop["purchase_date"]
    if not price or not pis:
        return None
    basis = price - land
    if basis <= 0:
        return None
    start = to_date(pis)
    if year < start.year:
        return 0
    annual = basis / 27.5
    first_year = annual * (12 - start.month + 0.5) / 12
    if year == start.year:
        return round(first_year)
    taken = first_year + annual * (year - start.year - 1)
    return round(max(min(annual, basis - taken), 0))


def schedule_e(year, split_shared=True):
    """Per-property Schedule E figures for a tax year.

    Returns {"properties": [...], "lines": [...], "totals": {...}, "shared": {...}}.
    Shared expenses (no property) are split evenly across the year's properties
    when split_shared is True; otherwise they're reported in their own column.
    """
    start, end = year_bounds(year)
    props = query("""SELECT * FROM properties
                     WHERE archived = 0 OR id IN (SELECT property_id FROM payments WHERE date BETWEEN ? AND ?)
                        OR id IN (SELECT property_id FROM expenses WHERE date BETWEEN ? AND ?)
                     ORDER BY name""", (start, end, start, end))
    ids = [p["id"] for p in props]

    rents = {r[0]: r[1] for r in query(
        f"SELECT property_id, SUM(amount_cents) FROM payments WHERE kind IN ({_INCOME_IN}) "
        "AND date BETWEEN ? AND ? GROUP BY property_id", (start, end))}
    exp = {}
    for r in query("SELECT property_id, category, SUM(amount_cents) AS t FROM expenses "
                   "WHERE date BETWEEN ? AND ? GROUP BY property_id, category", (start, end)):
        exp[(r["property_id"], r["category"])] = r["t"]

    shared = {c["key"]: exp.get((None, c["key"]), 0) for c in EXPENSE_CATEGORIES}
    n = len(ids)

    def split(cents, idx):
        # Even split that still adds up to the penny: the first properties absorb the remainder.
        if not split_shared or n == 0:
            return 0
        base, rem = divmod(cents, n)
        return base + (1 if idx < rem else 0)

    columns = []
    for idx, p in enumerate(props):
        col = {"property": p, "line3": rents.get(p["id"], 0), "cats": {}}
        for c in EXPENSE_CATEGORIES:
            col["cats"][c["key"]] = exp.get((p["id"], c["key"]), 0) + split(shared[c["key"]], idx)
        col["depreciation"] = depreciation_estimate(p, year)
        col["total_expenses"] = sum(col["cats"][k] for k in DEDUCTIBLE_KEYS)
        col["net_before_depr"] = col["line3"] - col["total_expenses"]
        col["line20"] = col["total_expenses"] + (col["depreciation"] or 0)
        col["net_after_depr"] = col["line3"] - col["line20"]
        columns.append(col)

    lines = [{"line": 3, "label": "Rents received", "key": "line3",
              "values": [c["line3"] for c in columns]}]
    for c in EXPENSE_CATEGORIES:
        if c["line"] is None:
            continue
        lines.append({"line": c["line"], "label": c["label"], "key": c["key"],
                      "values": [col["cats"][c["key"]] for col in columns],
                      "shared": shared[c["key"]]})
    lines.append({"line": 18, "label": "Depreciation (estimate)", "key": "depreciation", "estimate": True,
                  "values": [col["depreciation"] or 0 for col in columns], "shared": 0})
    lines.sort(key=lambda r: r["line"])

    not_deductible = [{"key": k, "label": CATEGORY_BY_KEY[k]["label"],
                       "values": [col["cats"][k] for col in columns], "shared": shared[k]}
                      for k in NON_DEDUCTIBLE_KEYS]

    totals = {
        "line3": sum(c["line3"] for c in columns),
        "expenses": sum(c["total_expenses"] for c in columns),
        "depreciation": sum(c["depreciation"] or 0 for c in columns),
        "shared": sum(shared[k] for k in DEDUCTIBLE_KEYS),
    }
    if not split_shared:
        totals["expenses"] += totals["shared"]
    totals["net_before_depr"] = totals["line3"] - totals["expenses"]
    totals["line20"] = totals["expenses"] + totals["depreciation"]
    totals["net_after_depr"] = totals["line3"] - totals["line20"]

    deposits_held = query("""SELECT COALESCE(SUM(amount_cents),0) FROM payments
                             WHERE kind = 'deposit' AND date <= ?""", (end,), one=True)[0] \
        - query("""SELECT COALESCE(SUM(amount_cents),0) FROM payments
                   WHERE kind = 'deposit_kept' AND date <= ?""", (end,), one=True)[0] \
        - query("""SELECT COALESCE(SUM(amount_cents),0) FROM expenses
                   WHERE category = 'deposit_refund' AND date <= ?""", (end,), one=True)[0]

    return {"year": year, "columns": columns, "lines": lines, "not_deductible": not_deductible,
            "totals": totals, "shared": shared, "split_shared": split_shared,
            "deposits_held": deposits_held}
