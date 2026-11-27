from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..constants import PROPERTY_TYPES
from ..db import execute, get_db, query, scalar
from ..ledger import (LEASE_SELECT, expense_total, income_total, lease_balance, lease_is_current,
                      rent_roll, year_bounds)
from ..utils import cents_plain, local_today, ym_of
from .common import FormErrors, date_field, f, float_field, get_or_404, int_field, money_field

bp = Blueprint("properties", __name__)

FIELDS = ["name", "address", "city", "state", "zip", "property_type", "owner_entity", "purchase_date",
          "purchase_price_cents", "land_value_cents", "placed_in_service", "mortgage_lender", "notes"]


def _parse():
    e = FormErrors()
    data = {
        "name": f("name"), "address": f("address"), "city": f("city"),
        "state": f("state", "IN").upper()[:2], "zip": f("zip"),
        "property_type": f("property_type", "single_family"), "owner_entity": f("owner_entity"),
        "purchase_date": date_field(e, "purchase_date", allow_blank=True),
        "purchase_price_cents": money_field(e, "purchase_price", allow_blank=True),
        "land_value_cents": money_field(e, "land_value", allow_blank=True),
        "placed_in_service": date_field(e, "placed_in_service", allow_blank=True),
        "mortgage_lender": f("mortgage_lender"), "notes": f("notes"),
    }
    if not data["name"]:
        e["name"] = "Give the property a short name, like “Maple St”."
    if data["property_type"] not in dict(PROPERTY_TYPES):
        data["property_type"] = "single_family"
    return data, e


def _form_from_row(p):
    d = dict(p)
    d["purchase_price"] = cents_plain(p["purchase_price_cents"])
    d["land_value"] = cents_plain(p["land_value_cents"])
    return d


@bp.route("/properties")
def index():
    today = local_today()
    start, end = year_bounds(today.year)
    show_archived = request.args.get("archived") == "1"
    props = query("SELECT * FROM properties WHERE archived = ? ORDER BY name", (1 if show_archived else 0,))
    rows = []
    for p in props:
        units = scalar("SELECT COUNT(*) FROM units WHERE property_id = ?", (p["id"],))
        occupied = scalar("""SELECT COUNT(DISTINCT l.unit_id) FROM leases l JOIN units u ON u.id = l.unit_id
                             WHERE u.property_id = ? AND l.start_date <= ?
                               AND (l.move_out_date IS NULL OR l.move_out_date >= ?)""",
                          (p["id"], today.isoformat(), today.isoformat()))
        inc = income_total(start, end, p["id"])
        exp = expense_total(start, end, p["id"])
        rows.append({"p": p, "units": units, "occupied": occupied, "income": inc, "net": inc - exp})
    archived_count = scalar("SELECT COUNT(*) FROM properties WHERE archived = 1")
    return render_template("properties/index.html", rows=rows, year=today.year,
                           show_archived=show_archived, archived_count=archived_count)


@bp.route("/properties/new", methods=["GET", "POST"])
def new():
    if request.method == "POST":
        data, e = _parse()
        unit_count = int_field(e, "unit_count", default=1, lo=1, hi=60)
        if not e:
            conn = get_db()
            cur = conn.execute(f"INSERT INTO properties ({','.join(FIELDS)}) VALUES ({','.join('?' * len(FIELDS))})",
                               [data[k] for k in FIELDS])
            pid = cur.lastrowid
            labels = ["Main"] if unit_count == 1 else [f"Unit {chr(65 + i)}" if unit_count <= 26 else f"Unit {i + 1}"
                                                     for i in range(unit_count)]
            conn.executemany("INSERT INTO units (property_id, label) VALUES (?, ?)", [(pid, lb) for lb in labels])
            conn.commit()
            flash(f"Added {data['name']}.", "ok")
            return redirect(url_for("properties.show", pid=pid))
        return render_template("properties/form.html", form=request.form, errors=e, types=PROPERTY_TYPES), 400
    return render_template("properties/form.html", form={"state": "IN", "unit_count": 1}, errors={},
                           types=PROPERTY_TYPES)


@bp.route("/properties/<int:pid>")
def show(pid):
    p = get_or_404("SELECT * FROM properties WHERE id = ?", (pid,))
    today = local_today()
    start, end = year_bounds(today.year)
    units = query("SELECT * FROM units WHERE property_id = ? ORDER BY label", (pid,))
    leases = query(LEASE_SELECT + " WHERE p.id = ? ORDER BY COALESCE(l.move_out_date, '9999') DESC, l.start_date DESC",
                   (pid,))
    current = {}
    past = []
    for l in leases:
        if lease_is_current(l, today) and l["unit_id"] not in current:
            current[l["unit_id"]] = {"lease": l, "balance": lease_balance(l, today)}
        elif not lease_is_current(l, today):
            past.append(l)
    future = [l for l in leases if l["start_date"] > today.isoformat()]
    inc, exp = income_total(start, end, pid), expense_total(start, end, pid)
    payments = query("""SELECT py.*, t.name AS tenant_name FROM payments py
                        LEFT JOIN leases l ON l.id = py.lease_id LEFT JOIN tenants t ON t.id = l.tenant_id
                        WHERE py.property_id = ? ORDER BY py.date DESC, py.id DESC LIMIT 10""", (pid,))
    expenses = query("SELECT * FROM expenses WHERE property_id = ? ORDER BY date DESC, id DESC LIMIT 10", (pid,))
    work = query("SELECT * FROM maintenance WHERE property_id = ? ORDER BY status = 'done', opened_on DESC LIMIT 10",
                 (pid,))
    files = query("SELECT * FROM files WHERE entity_type = 'property' AND entity_id = ? ORDER BY uploaded_at DESC",
                  (pid,))
    roll = rent_roll(ym_of(today), pid)
    return render_template("properties/show.html", p=p, units=units, current=current, past=past[:8],
                           future=future, income=inc, expenses_total=exp, year=today.year,
                           payments=payments, expenses=expenses, work=work, files=files, roll=roll,
                           types=dict(PROPERTY_TYPES))


@bp.route("/properties/<int:pid>/edit", methods=["GET", "POST"])
def edit(pid):
    p = get_or_404("SELECT * FROM properties WHERE id = ?", (pid,))
    if request.method == "POST":
        data, e = _parse()
        if not e:
            execute(f"UPDATE properties SET {', '.join(k + ' = ?' for k in FIELDS)} WHERE id = ?",
                    [data[k] for k in FIELDS] + [pid])
            flash("Saved.", "ok")
            return redirect(url_for("properties.show", pid=pid))
        return render_template("properties/form.html", form=request.form, errors=e, p=p, types=PROPERTY_TYPES), 400
    return render_template("properties/form.html", form=_form_from_row(p), errors={}, p=p, types=PROPERTY_TYPES)


@bp.route("/properties/<int:pid>/archive", methods=["POST"])
def archive(pid):
    p = get_or_404("SELECT * FROM properties WHERE id = ?", (pid,))
    execute("UPDATE properties SET archived = ? WHERE id = ?", (0 if p["archived"] else 1, pid))
    flash(f"{p['name']} {'restored' if p['archived'] else 'archived. Its history still counts in past tax years'}.", "ok")
    return redirect(url_for("properties.show", pid=pid))


@bp.route("/properties/<int:pid>/delete", methods=["POST"])
def delete(pid):
    p = get_or_404("SELECT * FROM properties WHERE id = ?", (pid,))
    money = scalar("SELECT (SELECT COUNT(*) FROM payments WHERE property_id = ?) + "
                   "(SELECT COUNT(*) FROM expenses WHERE property_id = ?)", (pid, pid))
    if money:
        flash("This property has payments or expenses, so it can't be deleted. Archive it instead.", "error")
        return redirect(url_for("properties.show", pid=pid))
    execute("DELETE FROM properties WHERE id = ?", (pid,))
    flash(f"Deleted {p['name']}.", "ok")
    return redirect(url_for("properties.index"))


# ---------- units ----------

def _parse_unit():
    e = FormErrors()
    data = {"label": f("label") or "Main", "beds": float_field(e, "beds"), "baths": float_field(e, "baths"),
            "sqft": int_field(e, "sqft", lo=0, hi=1_000_000),
            "market_rent_cents": money_field(e, "market_rent", allow_blank=True), "notes": f("notes")}
    return data, e


@bp.route("/properties/<int:pid>/units/new", methods=["GET", "POST"])
def unit_new(pid):
    p = get_or_404("SELECT * FROM properties WHERE id = ?", (pid,))
    if request.method == "POST":
        data, e = _parse_unit()
        if not e:
            execute("INSERT INTO units (property_id, label, beds, baths, sqft, market_rent_cents, notes) "
                    "VALUES (?,?,?,?,?,?,?)", (pid, data["label"], data["beds"], data["baths"], data["sqft"],
                                               data["market_rent_cents"], data["notes"]))
            flash(f"Added {data['label']}.", "ok")
            return redirect(url_for("properties.show", pid=pid))
        return render_template("properties/unit_form.html", p=p, form=request.form, errors=e), 400
    return render_template("properties/unit_form.html", p=p, form={}, errors={})


@bp.route("/units/<int:uid>/edit", methods=["GET", "POST"])
def unit_edit(uid):
    u = get_or_404("SELECT * FROM units WHERE id = ?", (uid,))
    p = get_or_404("SELECT * FROM properties WHERE id = ?", (u["property_id"],))
    if request.method == "POST":
        data, e = _parse_unit()
        if not e:
            execute("UPDATE units SET label=?, beds=?, baths=?, sqft=?, market_rent_cents=?, notes=? WHERE id=?",
                    (data["label"], data["beds"], data["baths"], data["sqft"], data["market_rent_cents"],
                     data["notes"], uid))
            flash("Saved.", "ok")
            return redirect(url_for("properties.show", pid=p["id"]))
        return render_template("properties/unit_form.html", p=p, u=u, form=request.form, errors=e), 400
    form = dict(u)
    form["market_rent"] = cents_plain(u["market_rent_cents"])
    for k in ("beds", "baths"):
        if form[k] is not None and float(form[k]).is_integer():
            form[k] = int(form[k])
    return render_template("properties/unit_form.html", p=p, u=u, form=form, errors={})


@bp.route("/units/<int:uid>/delete", methods=["POST"])
def unit_delete(uid):
    u = get_or_404("SELECT * FROM units WHERE id = ?", (uid,))
    if scalar("SELECT COUNT(*) FROM leases WHERE unit_id = ?", (uid,)):
        flash("This unit has tenant history, so it can't be deleted.", "error")
    elif scalar("SELECT COUNT(*) FROM units WHERE property_id = ?", (u["property_id"],)) <= 1:
        flash("A property needs at least one unit.", "error")
    else:
        execute("DELETE FROM units WHERE id = ?", (uid,))
        flash(f"Deleted {u['label']}.", "ok")
    return redirect(url_for("properties.show", pid=u["property_id"]))
