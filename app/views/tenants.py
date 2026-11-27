from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..db import execute, get_db, query, scalar
from ..ledger import LEASE_SELECT, lease_balance, lease_is_current, lease_months, place_label
from ..utils import cents_plain, local_today, ym_of
from .common import (FormErrors, date_field, f, get_or_404, id_field, int_field, money_field,
                     unit_options, ym_field)

bp = Blueprint("tenants", __name__)

LEASE_FIELDS = ["unit_id", "start_date", "end_date", "rent_cents", "due_day", "grace_days", "late_fee_cents",
                "deposit_cents", "section8", "hap_cents", "housing_authority", "s8_case_number",
                "ledger_start", "opening_balance_cents", "notes"]


def _parse_tenant(e):
    data = {"name": f("name"), "phone": f("phone"), "email": f("email"), "notes": f("tenant_notes")}
    if not data["name"]:
        e["name"] = "Enter the tenant's name."
    return data


def _parse_lease(e):
    today = local_today()
    data = {
        "unit_id": id_field("unit_id"),
        "start_date": date_field(e, "start_date"),
        "end_date": date_field(e, "end_date", allow_blank=True),
        "rent_cents": money_field(e, "rent"),
        "due_day": int_field(e, "due_day", default=1, lo=1, hi=28),
        "grace_days": int_field(e, "grace_days", default=5, lo=0, hi=27),
        "late_fee_cents": money_field(e, "late_fee", allow_blank=True) or 0,
        "deposit_cents": money_field(e, "deposit", allow_blank=True) or 0,
        "section8": 1 if request.form.get("section8") else 0,
        "hap_cents": money_field(e, "hap", allow_blank=True) or 0,
        "housing_authority": f("housing_authority"),
        "s8_case_number": f("s8_case_number"),
        "ledger_start": ym_field(e, "ledger_start", allow_blank=True),
        "opening_balance_cents": money_field(e, "opening_balance", allow_blank=True) or 0,
        "notes": f("lease_notes"),
    }
    if not data["unit_id"] or not scalar("SELECT 1 FROM units WHERE id = ?", (data["unit_id"],)):
        e["unit_id"] = "Pick the property (and unit) they rent."
    if data["rent_cents"] is not None and data["rent_cents"] < 0:
        e["rent"] = "Rent can't be negative."
    if data["start_date"] and data["end_date"] and data["end_date"] < data["start_date"]:
        e["end_date"] = "Lease end is before the start."
    if not data["section8"]:
        data["hap_cents"] = 0
    elif data["rent_cents"] is not None and data["hap_cents"] > data["rent_cents"]:
        e["hap"] = "The housing authority's part can't be more than the total rent."
    if not data["ledger_start"] and data["start_date"]:
        # Default: track balances from this month, or from the lease start if it's newer.
        data["ledger_start"] = max(ym_of(data["start_date"]), ym_of(today))
    return data


def _lease_form(l):
    d = dict(l)
    for k in ("rent", "late_fee", "deposit", "hap", "opening_balance"):
        d[k] = cents_plain(l[f"{k}_cents"])
    d["lease_notes"] = l["notes"]
    return d


@bp.route("/tenants")
def index():
    today = local_today()
    rows = query(LEASE_SELECT + " WHERE p.archived = 0 ORDER BY t.name, l.start_date DESC")
    current, seen = [], set()
    for l in rows:
        if lease_is_current(l, today) or l["start_date"] > today.isoformat():
            current.append({"lease": l, "place": place_label(l), "balance": lease_balance(l, today),
                            "upcoming": l["start_date"] > today.isoformat()})
            seen.add(l["tenant_id"])
    past = query("""SELECT t.*, MAX(l.move_out_date) AS moved_out FROM tenants t
                    LEFT JOIN leases l ON l.tenant_id = t.id GROUP BY t.id ORDER BY moved_out DESC, t.name""")
    past = [t for t in past if t["id"] not in seen]
    owed = sum(r["balance"] for r in current if r["balance"] > 0)
    return render_template("tenants/index.html", current=current, past=past, owed=owed)


@bp.route("/tenants/new", methods=["GET", "POST"])
def new():
    units = unit_options()
    if not units:
        flash("Add a property first, then its tenants.", "error")
        return redirect(url_for("properties.new"))
    if request.method == "POST":
        e = FormErrors()
        t = _parse_tenant(e)
        l = _parse_lease(e)
        if not e:
            conn = get_db()
            tid = conn.execute("INSERT INTO tenants (name, phone, email, notes) VALUES (?,?,?,?)",
                               (t["name"], t["phone"], t["email"], t["notes"])).lastrowid
            l["tenant_id"] = tid
            cols = LEASE_FIELDS + ["tenant_id"]
            conn.execute(f"INSERT INTO leases ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         [l[k] for k in cols])
            conn.commit()
            flash(f"Added {t['name']}.", "ok")
            return redirect(url_for("tenants.show", tid=tid))
        return render_template("tenants/new.html", form=request.form, errors=e, units=units), 400
    form = {"unit_id": request.args.get("unit_id", ""), "due_day": 1, "grace_days": 5}
    return render_template("tenants/new.html", form=form, errors={}, units=units)


@bp.route("/tenants/<int:tid>")
def show(tid):
    t = get_or_404("SELECT * FROM tenants WHERE id = ?", (tid,))
    today = local_today()
    leases = query(LEASE_SELECT + " WHERE l.tenant_id = ? ORDER BY l.start_date DESC", (tid,))
    lease_rows = []
    for l in leases:
        lease_rows.append({"lease": l, "place": place_label(l), "current": lease_is_current(l, today),
                           "balance": lease_balance(l, today), "months": lease_months(l, today)[:12]})
    payments = query("""SELECT py.*, p.name AS property_name FROM payments py
                        JOIN properties p ON p.id = py.property_id
                        WHERE py.lease_id IN (SELECT id FROM leases WHERE tenant_id = ?)
                        ORDER BY py.date DESC, py.id DESC LIMIT 50""", (tid,))
    work = query("SELECT m.*, p.name AS property_name FROM maintenance m JOIN properties p ON p.id = m.property_id "
                 "WHERE m.tenant_id = ? ORDER BY m.opened_on DESC", (tid,))
    files = query("SELECT * FROM files WHERE entity_type = 'tenant' AND entity_id = ? ORDER BY uploaded_at DESC",
                  (tid,))
    return render_template("tenants/show.html", t=t, leases=lease_rows, payments=payments, work=work,
                           files=files, today=today)


@bp.route("/tenants/<int:tid>/edit", methods=["GET", "POST"])
def edit(tid):
    t = get_or_404("SELECT * FROM tenants WHERE id = ?", (tid,))
    if request.method == "POST":
        e = FormErrors()
        data = _parse_tenant(e)
        if not e:
            execute("UPDATE tenants SET name=?, phone=?, email=?, notes=? WHERE id=?",
                    (data["name"], data["phone"], data["email"], data["notes"], tid))
            flash("Saved.", "ok")
            return redirect(url_for("tenants.show", tid=tid))
        return render_template("tenants/edit.html", t=t, form=request.form, errors=e), 400
    form = dict(t)
    form["tenant_notes"] = t["notes"]
    return render_template("tenants/edit.html", t=t, form=form, errors={})


@bp.route("/tenants/<int:tid>/delete", methods=["POST"])
def delete(tid):
    t = get_or_404("SELECT * FROM tenants WHERE id = ?", (tid,))
    n = scalar("SELECT COUNT(*) FROM payments WHERE lease_id IN (SELECT id FROM leases WHERE tenant_id = ?)", (tid,))
    if n and request.form.get("confirm") != "yes":
        flash(f"{t['name']} has {n} payments. They'll stay in your income totals but lose the tenant name.", "error")
        return redirect(url_for("tenants.show", tid=tid))
    execute("DELETE FROM tenants WHERE id = ?", (tid,))
    flash(f"Deleted {t['name']}.", "ok")
    return redirect(url_for("tenants.index"))


@bp.route("/tenants/<int:tid>/leases/new", methods=["GET", "POST"])
def lease_new(tid):
    t = get_or_404("SELECT * FROM tenants WHERE id = ?", (tid,))
    units = unit_options()
    if request.method == "POST":
        e = FormErrors()
        l = _parse_lease(e)
        if not e:
            l["tenant_id"] = tid
            cols = LEASE_FIELDS + ["tenant_id"]
            execute(f"INSERT INTO leases ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [l[k] for k in cols])
            flash("Lease added.", "ok")
            return redirect(url_for("tenants.show", tid=tid))
        return render_template("tenants/lease_form.html", t=t, form=request.form, errors=e, units=units), 400
    prev = query("SELECT * FROM leases WHERE tenant_id = ? ORDER BY start_date DESC LIMIT 1", (tid,), one=True)
    form = _lease_form(prev) if prev else {"due_day": 1, "grace_days": 5}
    for k in ("start_date", "end_date", "move_out_date", "ledger_start", "opening_balance", "lease_notes"):
        form.pop(k, None)
    return render_template("tenants/lease_form.html", t=t, form=form, errors={}, units=units, renewal=bool(prev))


@bp.route("/leases/<int:lid>/edit", methods=["GET", "POST"])
def lease_edit(lid):
    l = get_or_404("SELECT * FROM leases WHERE id = ?", (lid,))
    t = get_or_404("SELECT * FROM tenants WHERE id = ?", (l["tenant_id"],))
    units = unit_options()
    if request.method == "POST":
        e = FormErrors()
        data = _parse_lease(e)
        move_out = date_field(e, "move_out_date", allow_blank=True)
        if move_out and data.get("start_date") and move_out < data["start_date"]:
            e["move_out_date"] = "Move-out is before the lease started."
        if not e:
            execute(f"UPDATE leases SET {', '.join(k + ' = ?' for k in LEASE_FIELDS)}, move_out_date = ? WHERE id = ?",
                    [data[k] for k in LEASE_FIELDS] + [move_out, lid])
            if data["unit_id"] != l["unit_id"]:
                new_pid = scalar("SELECT property_id FROM units WHERE id = ?", (data["unit_id"],))
                execute("UPDATE payments SET property_id = ? WHERE lease_id = ?", (new_pid, lid))
            flash("Lease saved.", "ok")
            return redirect(url_for("tenants.show", tid=t["id"]))
        return render_template("tenants/lease_form.html", t=t, l=l, form=request.form, errors=e, units=units), 400
    return render_template("tenants/lease_form.html", t=t, l=l, form=_lease_form(l), errors={}, units=units)


@bp.route("/leases/<int:lid>/move-out", methods=["POST"])
def move_out(lid):
    l = get_or_404("SELECT * FROM leases WHERE id = ?", (lid,))
    e = FormErrors()
    d = date_field(e, "move_out_date")
    if e or (d and d < l["start_date"]):
        flash(e.get("move_out_date") or "Move-out is before the lease started.", "error")
    else:
        execute("UPDATE leases SET move_out_date = ? WHERE id = ?", (d, lid))
        flash("Marked as moved out. Rent stops being expected after that month.", "ok")
    return redirect(url_for("tenants.show", tid=l["tenant_id"]))


@bp.route("/leases/<int:lid>/delete", methods=["POST"])
def lease_delete(lid):
    l = get_or_404("SELECT * FROM leases WHERE id = ?", (lid,))
    execute("DELETE FROM leases WHERE id = ?", (lid,))
    flash("Lease deleted. Its payments are still in your income.", "ok")
    return redirect(url_for("tenants.show", tid=l["tenant_id"]))
