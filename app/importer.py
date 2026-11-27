"""Bulk CSV import for properties, tenants, payments and expenses.

Used by the web Import page and by `python manage.py import`. Each importer
turns raw CSV rows into checked rows: {"n", "show", "data", "error", "dupe"}.
Nothing is written until commit() is called with those rows.
"""
import csv
import io
import re

from .constants import (CATEGORY_ALIASES, CATEGORY_BY_KEY, EXPENSE_CATEGORIES, KIND_ALIASES, KIND_BY_KEY,
                        PAYMENT_KINDS, RENT_KINDS)
from .db import get_db
from .utils import fmt_money, local_today, parse_date, parse_money, parse_ym, ym_of

HEADER_ALIASES = {
    "date": ["date", "paid_on", "date_paid", "payment_date", "paid", "day"],
    "amount": ["amount", "amt", "total", "amount_paid", "paid_amount", "cost", "price", "value"],
    "tenant": ["tenant", "tenant_name", "from", "payer", "paid_by", "resident"],
    "property": ["property", "property_name", "building", "house", "address", "location"],
    "unit": ["unit", "apt", "apartment", "unit_label"],
    "month": ["month", "for_month", "period", "applies_to", "rent_month", "for"],
    "type": ["type", "kind", "payment_type"],
    "category": ["category", "expense_type", "schedule_e", "cat"],
    "vendor": ["vendor", "payee", "paid_to", "company", "contractor"],
    "method": ["method", "payment_method", "via", "how"],
    "reference": ["reference", "ref", "check", "check_number", "check_no", "confirmation"],
    "notes": ["notes", "note", "memo", "description", "details"],
    "name": ["name", "nickname", "property_name", "tenant_name", "full_name"],
    "city": ["city", "town"], "state": ["state", "st"], "zip": ["zip", "zipcode", "zip_code", "postal_code"],
    "units": ["units", "unit_count", "number_of_units", "doors"],
    "owner": ["owner", "owner_entity", "llc", "entity", "titled_to"],
    "purchase_date": ["purchase_date", "bought", "date_purchased", "acquired"],
    "purchase_price": ["purchase_price", "price_paid", "cost_basis", "purchase"],
    "land_value": ["land_value", "land"],
    "lender": ["lender", "mortgage_lender", "bank", "servicer"],
    "phone": ["phone", "phone_number", "cell", "mobile"],
    "email": ["email", "e-mail", "email_address"],
    "lease_start": ["lease_start", "start", "start_date", "move_in", "move_in_date"],
    "lease_end": ["lease_end", "end", "end_date", "lease_expires", "expires"],
    "rent": ["rent", "monthly_rent", "rent_amount", "total_rent"],
    "deposit": ["deposit", "security_deposit", "sd"],
    "due_day": ["due_day", "due", "due_on"],
    "section8": ["section8", "section_8", "s8", "voucher"],
    "hap": ["hap", "hap_amount", "housing_portion", "section8_amount", "s8_amount"],
    "housing_authority": ["housing_authority", "pha", "authority"],
    "case_number": ["case_number", "case", "s8_case", "voucher_number"],
    "track_from": ["track_from", "ledger_start", "balance_from"],
    "opening_balance": ["opening_balance", "balance", "owes", "past_due"],
}

KINDS = {
    "properties": ["name", "address", "city", "state", "zip", "units", "owner", "purchase_date", "purchase_price",
                   "land_value", "lender", "notes"],
    "tenants": ["name", "phone", "email", "property", "unit", "lease_start", "lease_end", "rent", "deposit",
                "due_day", "section8", "hap", "housing_authority", "case_number", "track_from", "opening_balance",
                "notes"],
    "payments": ["date", "tenant", "property", "amount", "type", "month", "method", "reference", "notes"],
    "expenses": ["date", "property", "category", "vendor", "amount", "method", "reference", "notes"],
}
REQUIRED = {"properties": ["name"], "tenants": ["name", "property", "lease_start", "rent"],
            "payments": ["date", "amount"], "expenses": ["date", "amount", "category"]}

EXAMPLES = {
    "properties": [["Maple St", "123 Maple St", "Gary", "IN", "46402", "1", "Personal", "2019-06-14", "85000",
                    "12000", "Chase", ""],
                   ["Elm Duplex", "45 Elm Ave", "Hammond", "IN", "46320", "2", "Personal", "2021-03-01",
                    "140000", "20000", "", ""]],
    "tenants": [["Jane Doe", "219-555-0100", "jane@example.com", "Maple St", "", "2025-08-01", "2026-07-31",
                 "1200", "1200", "1", "no", "", "", "", "2026-01", "0", ""],
                ["John Roe", "", "", "Elm Duplex", "Unit A", "2024-02-01", "", "1050", "500", "1", "yes", "850",
                 "Gary Housing Authority", "S8-1234", "2026-01", "0", "Month to month"]],
    "payments": [["2026-01-03", "Jane Doe", "", "1200", "rent", "2026-01", "Zelle", "", ""],
                 ["2026-01-02", "John Roe", "", "850", "section 8", "2026-01", "ACH / bank transfer", "", "HAP"],
                 ["2026-01-05", "John Roe", "", "200", "rent", "2026-01", "Cash", "", "Tenant portion"]],
    "expenses": [["2026-01-10", "Maple St", "repairs", "Joe's Plumbing", "185.00", "Check", "1043", "Kitchen leak"],
                 ["2026-01-15", "", "legal_professional", "Smith CPA", "450", "Card", "", "Shared: tax prep"]],
}


def template_csv(kind):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(KINDS[kind])
    w.writerows(EXAMPLES[kind])
    return buf.getvalue()


def _norm(h):
    return re.sub(r"[^a-z0-9]+", "_", (h or "").strip().lower()).strip("_")


def read_csv(text, kind):
    """-> (rows as dicts keyed by our field names, unknown headers)."""
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], []
    wanted = KINDS[kind]
    mapping, unknown = {}, []
    for i, h in enumerate(header):
        n = _norm(h)
        field = n if n in wanted else next((f for f in wanted if n in HEADER_ALIASES.get(f, [])), None)
        if field and field not in mapping.values():
            mapping[i] = field
        elif h.strip():
            unknown.append(h.strip())
    rows = []
    for raw in reader:
        if not any(c.strip() for c in raw):
            continue
        rows.append({mapping[i]: (raw[i].strip() if i < len(raw) else "") for i in mapping})
    return rows, unknown


# ---------- matching ----------

def _properties():
    return get_db().execute("SELECT id, name, address FROM properties").fetchall()


def find_property(text, props=None):
    if not text:
        return None
    t = text.strip().lower()
    props = props if props is not None else _properties()
    for key in ("name", "address"):
        for p in props:
            if (p[key] or "").strip().lower() == t:
                return p["id"]
    hits = [p["id"] for p in props if t in (p["name"] or "").lower() or (p["address"] or "").lower().startswith(t)]
    return hits[0] if len(hits) == 1 else None


def find_unit(property_id, label):
    db = get_db()
    units = db.execute("SELECT id, label FROM units WHERE property_id = ? ORDER BY id", (property_id,)).fetchall()
    if not units:
        return None
    if not label:
        return units[0]["id"] if len(units) == 1 else None
    t = label.strip().lower()
    for u in units:
        lab = u["label"].lower()
        if lab == t or lab.replace("unit ", "") == t.replace("unit ", ""):
            return u["id"]
    return None


def find_lease(tenant, property_id, on_date):
    db = get_db()
    sql = """SELECT l.*, u.property_id FROM leases l JOIN tenants t ON t.id = l.tenant_id
             JOIN units u ON u.id = l.unit_id WHERE lower(trim(t.name)) = ?"""
    args = [tenant.strip().lower()]
    if property_id:
        sql += " AND u.property_id = ?"
        args.append(property_id)
    leases = db.execute(sql + " ORDER BY l.start_date DESC", args).fetchall()
    if not leases:
        return None
    for l in leases:
        if l["start_date"] <= on_date and (not l["move_out_date"] or l["move_out_date"] >= on_date[:8] + "01"):
            return l
    return leases[0]


def _kind(text):
    t = (text or "rent").strip().lower()
    if t in KIND_BY_KEY:
        return t
    if t in KIND_ALIASES:
        return KIND_ALIASES[t]
    for k in PAYMENT_KINDS:
        if k["label"].lower() == t:
            return k["key"]
    raise ValueError(f"Type “{text}” isn't one of: rent, section 8, late fee, deposit, deposit kept, other.")


def _category(text):
    t = (text or "").strip().lower()
    if t in CATEGORY_BY_KEY:
        return t
    for c in EXPENSE_CATEGORIES:
        if c["label"].lower() == t:
            return c["key"]
    if t in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[t]
    raise ValueError(f"Category “{text}” isn't recognized. Use one from the list below the upload box.")


def _yes(text):
    return (text or "").strip().lower() in ("y", "yes", "true", "1", "x", "section 8", "s8")


# ---------- per-kind preparation ----------

def _missing(kind, row):
    return [f for f in REQUIRED[kind] if not row.get(f)]


def prepare(kind, rows):
    props = _properties()
    out = []
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        item = {"n": n, "show": [row.get(k, "") for k in KINDS[kind]], "data": None, "error": None, "dupe": False}
        miss = _missing(kind, row)
        if miss:
            item["error"] = "Missing " + ", ".join(miss) + "."
            out.append(item)
            continue
        try:
            item["data"], item["dupe"] = PREPARERS[kind](row, props)
        except ValueError as e:
            item["error"] = str(e)
        out.append(item)
    return out


def _prep_property(row, props):
    names = {p["name"].strip().lower() for p in props}
    if row["name"].strip().lower() in names:
        return None, True
    units = int(float(row.get("units") or 1))
    if not 1 <= units <= 60:
        raise ValueError("Units must be 1 to 60.")
    ptype = "single_family" if units == 1 else ("duplex" if units == 2 else "triplex" if units == 3 else
                                                "fourplex" if units == 4 else "multi")
    return {"name": row["name"], "address": row.get("address", ""), "city": row.get("city", ""),
            "state": (row.get("state") or "IN").upper()[:2], "zip": row.get("zip", ""), "property_type": ptype,
            "owner_entity": row.get("owner", ""),
            "purchase_date": parse_date(row.get("purchase_date"), allow_blank=True),
            "purchase_price_cents": parse_money(row.get("purchase_price"), allow_blank=True),
            "land_value_cents": parse_money(row.get("land_value"), allow_blank=True),
            "mortgage_lender": row.get("lender", ""), "notes": row.get("notes", ""), "_units": units}, False


def _prep_tenant(row, props):
    pid = find_property(row["property"], props)
    if not pid:
        raise ValueError(f"No property matches “{row['property']}”. Add it first or fix the spelling.")
    uid = find_unit(pid, row.get("unit"))
    if not uid:
        raise ValueError(f"Couldn't match unit “{row.get('unit', '')}”. Multi-unit properties need the unit, "
                         "spelled like it is in PropFlow (e.g. “Unit A”).")
    start = parse_date(row["lease_start"])
    s8 = _yes(row.get("section8")) or bool(row.get("hap"))
    rent = parse_money(row["rent"])
    hap = parse_money(row.get("hap"), allow_blank=True) or 0 if s8 else 0
    if hap > rent:
        raise ValueError("HAP is more than the total rent.")
    track = parse_ym(row.get("track_from"), allow_blank=True) or max(ym_of(start), ym_of(local_today()))
    dupe = get_db().execute("""SELECT 1 FROM leases l JOIN tenants t ON t.id = l.tenant_id
                               WHERE lower(t.name) = ? AND l.unit_id = ? AND l.start_date = ?""",
                            (row["name"].strip().lower(), uid, start)).fetchone() is not None
    return {"tenant": {"name": row["name"], "phone": row.get("phone", ""), "email": row.get("email", ""),
                       "notes": ""},
            "lease": {"unit_id": uid, "start_date": start,
                      "end_date": parse_date(row.get("lease_end"), allow_blank=True), "rent_cents": rent,
                      "due_day": int(row.get("due_day") or 1), "deposit_cents": parse_money(row.get("deposit"), allow_blank=True) or 0,
                      "section8": 1 if s8 else 0, "hap_cents": hap,
                      "housing_authority": row.get("housing_authority", ""), "s8_case_number": row.get("case_number", ""),
                      "ledger_start": track,
                      "opening_balance_cents": parse_money(row.get("opening_balance"), allow_blank=True) or 0,
                      "notes": row.get("notes", "")}}, dupe


def _prep_payment(row, props):
    date = parse_date(row["date"])
    amount = parse_money(row["amount"])
    kind = _kind(row.get("type"))
    pid = find_property(row.get("property"), props) if row.get("property") else None
    if row.get("property") and not pid:
        raise ValueError(f"No property matches “{row['property']}”.")
    lease = None
    if row.get("tenant"):
        lease = find_lease(row["tenant"], pid, date)
        if not lease:
            raise ValueError(f"No tenant named “{row['tenant']}”{' at that property' if pid else ''}.")
        pid = lease["property_id"]
    if kind in RENT_KINDS and not lease:
        raise ValueError("Rent and Section 8 rows need a tenant name.")
    if not pid:
        raise ValueError("Give a tenant or a property.")
    applies = parse_ym(row.get("month"), allow_blank=True)
    if kind in RENT_KINDS and not applies:
        applies = ym_of(date)
    data = {"date": date, "property_id": pid, "lease_id": lease["id"] if lease else None, "kind": kind,
            "amount_cents": amount, "applies_to": applies, "method": row.get("method", ""),
            "reference": row.get("reference", ""), "notes": row.get("notes", "")}
    dupe = get_db().execute("""SELECT 1 FROM payments WHERE date = ? AND property_id = ? AND amount_cents = ?
                               AND kind = ? AND COALESCE(lease_id, 0) = ?""",
                            (date, pid, amount, kind, data["lease_id"] or 0)).fetchone() is not None
    return data, dupe


def _prep_expense(row, props):
    date = parse_date(row["date"])
    amount = parse_money(row["amount"])
    cat = _category(row["category"])
    raw = (row.get("property") or "").strip()
    pid = None
    if raw and raw.lower() not in ("shared", "all", "all properties", "portfolio", "none"):
        pid = find_property(raw, props)
        if not pid:
            raise ValueError(f"No property matches “{raw}”. Leave it blank or write “shared” for portfolio-wide.")
    vendor = row.get("vendor", "")
    cid = get_db().execute("SELECT id FROM contacts WHERE name = ? COLLATE NOCASE", (vendor,)).fetchone() if vendor else None
    data = {"date": date, "property_id": pid, "category": cat, "vendor": vendor, "contact_id": cid[0] if cid else None,
            "amount_cents": amount, "method": row.get("method", ""), "reference": row.get("reference", ""),
            "notes": row.get("notes", "")}
    dupe = get_db().execute("""SELECT 1 FROM expenses WHERE date = ? AND COALESCE(property_id, 0) = ?
                               AND amount_cents = ? AND category = ?""",
                            (date, pid or 0, amount, cat)).fetchone() is not None
    return data, dupe


PREPARERS = {"properties": _prep_property, "tenants": _prep_tenant, "payments": _prep_payment,
             "expenses": _prep_expense}


def commit(kind, items, include_dupes=False):
    """Insert the good rows in one transaction. Returns how many were added."""
    db = get_db()
    added = 0
    try:
        for it in items:
            if it["error"] or not it["data"] or (it["dupe"] and not include_dupes):
                continue
            d = dict(it["data"])
            if kind == "properties":
                units = d.pop("_units")
                cols = list(d)
                pid = db.execute(f"INSERT INTO properties ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                 [d[c] for c in cols]).lastrowid
                labels = ["Main"] if units == 1 else [f"Unit {chr(65 + i)}" for i in range(units)] if units <= 26 \
                    else [f"Unit {i + 1}" for i in range(units)]
                db.executemany("INSERT INTO units (property_id, label) VALUES (?, ?)", [(pid, lb) for lb in labels])
            elif kind == "tenants":
                t = d["tenant"]
                existing = db.execute("SELECT id FROM tenants WHERE lower(name) = ?", (t["name"].lower(),)).fetchone()
                tid = existing[0] if existing else db.execute(
                    "INSERT INTO tenants (name, phone, email, notes) VALUES (?,?,?,?)",
                    (t["name"], t["phone"], t["email"], t["notes"])).lastrowid
                lease = dict(d["lease"], tenant_id=tid)
                cols = list(lease)
                db.execute(f"INSERT INTO leases ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           [lease[c] for c in cols])
            else:
                table = "payments" if kind == "payments" else "expenses"
                cols = list(d)
                db.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                           [d[c] for c in cols])
            added += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return added


def summarize(kind, items):
    good = [i for i in items if not i["error"] and not i["dupe"]]
    total = None
    if kind in ("payments", "expenses"):
        total = fmt_money(sum(i["data"]["amount_cents"] for i in good))
    return {"rows": len(items), "ready": len(good), "errors": sum(1 for i in items if i["error"]),
            "dupes": sum(1 for i in items if i["dupe"] and not i["error"]), "total": total}

