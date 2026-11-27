"""Shared bits for views: dropdown options, form parsing, 404 helpers."""
from flask import abort, request

from ..db import query
from ..ledger import LEASE_SELECT, place_label
from ..utils import local_today, parse_date, parse_money, parse_ym


def get_or_404(sql, args):
    row = query(sql, args, one=True)
    if row is None:
        abort(404)
    return row


def property_options(include_archived=False):
    sql = "SELECT id, name, address FROM properties"
    if not include_archived:
        sql += " WHERE archived = 0"
    return query(sql + " ORDER BY name")


def unit_options():
    rows = query("""SELECT u.id, u.label, p.name AS property_name,
                           (SELECT COUNT(*) FROM units u2 WHERE u2.property_id = p.id) AS n
                    FROM units u JOIN properties p ON p.id = u.property_id
                    WHERE p.archived = 0 ORDER BY p.name, u.label""")
    return [{"id": r["id"], "label": r["property_name"] if r["n"] == 1 else f"{r['property_name']}, {r['label']}"}
            for r in rows]


def lease_options(include_past=False):
    """Leases for the 'who paid' dropdown: current tenants first."""
    today = local_today().isoformat()
    sql = LEASE_SELECT + " WHERE p.archived = 0"
    if not include_past:
        sql += " AND (l.move_out_date IS NULL OR l.move_out_date >= date(?, '-120 days'))"
        rows = query(sql + " ORDER BY t.name", (today,))
    else:
        rows = query(sql + " ORDER BY t.name")
    out = []
    for r in rows:
        out.append({"id": r["id"], "label": f"{r['tenant_name']} · {place_label(r)}",
                    "property_id": r["property_id"], "rent": r["rent_cents"],
                    "hap": r["hap_cents"] if r["section8"] else 0,
                    "moved_out": bool(r["move_out_date"] and r["move_out_date"] < today)})
    return out


def contact_names():
    return [r["name"] for r in query("SELECT name FROM contacts ORDER BY name")]


class FormErrors(dict):
    """Collects per-field messages while parsing a submitted form."""

    def take(self, field, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            self[field] = str(e)
            return None


def f(name, default=""):
    return (request.form.get(name) or default).strip()


def money_field(errors, name, allow_blank=False):
    return errors.take(name, parse_money, request.form.get(name), allow_blank=allow_blank)


def date_field(errors, name, allow_blank=False):
    return errors.take(name, parse_date, request.form.get(name), allow_blank=allow_blank)


def ym_field(errors, name, allow_blank=False):
    return errors.take(name, parse_ym, request.form.get(name), allow_blank=allow_blank)


def int_field(errors, name, default=None, lo=None, hi=None):
    raw = f(name)
    if not raw:
        return default
    try:
        v = int(float(raw))
    except ValueError:
        errors[name] = "Enter a whole number."
        return default
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        errors[name] = f"Use a number from {lo} to {hi}."
    return v


def float_field(errors, name):
    raw = f(name)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        errors[name] = "Enter a number."
        return None


def id_field(name):
    raw = f(name)
    return int(raw) if raw.isdigit() else None


def year_arg(default=None):
    raw = request.args.get("year", "")
    if raw.isdigit() and 1990 <= int(raw) <= 2100:
        return int(raw)
    return default or local_today().year


def years_with_data():
    rows = query("""SELECT DISTINCT substr(date,1,4) AS y FROM payments
                    UNION SELECT DISTINCT substr(date,1,4) FROM expenses ORDER BY y DESC""")
    years = {int(r["y"]) for r in rows if r["y"] and r["y"].isdigit()}
    years.add(local_today().year)
    return sorted(years, reverse=True)
