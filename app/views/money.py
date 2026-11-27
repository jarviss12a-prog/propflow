"""Payments (money in), expenses (money out), the monthly rent roll and the mortgage splitter."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..constants import (CATEGORY_BY_KEY, EXPENSE_CATEGORIES, INCOME_KINDS, KIND_BY_KEY, PAYMENT_KINDS,
                         PAYMENT_METHODS, RENT_KINDS)
from ..db import execute, get_db, query, scalar
from ..ledger import rent_roll, rent_roll_summary
from ..storage import delete_stored, save_upload
from ..utils import add_months, cents_plain, local_today, parse_ym, ym_of
from .common import (FormErrors, contact_names, date_field, f, get_or_404, id_field, lease_options,
                     money_field, property_options, year_arg, years_with_data, ym_field)

bp = Blueprint("money", __name__)


# ---------- rent roll ----------

@bp.route("/rent")
def rent():
    today = local_today()
    try:
        ym = parse_ym(request.args.get("month") or ym_of(today))
    except ValueError:
        ym = ym_of(today)
    pid = request.args.get("property", type=int)
    rows = rent_roll(ym, pid)
    return render_template("rent.html", ym=ym, rows=rows, summary=rent_roll_summary(rows),
                           prev=add_months(ym, -1), next=add_months(ym, 1), this=ym_of(today),
                           properties=property_options(), pid=pid)


# ---------- payments ----------

PAYMENT_COLS = ["date", "property_id", "lease_id", "kind", "amount_cents", "applies_to", "method", "reference",
                "notes"]


def _parse_payment():
    e = FormErrors()
    data = {
        "date": date_field(e, "date"),
        "lease_id": id_field("lease_id"),
        "property_id": id_field("property_id"),
        "kind": f("kind", "rent"),
        "amount_cents": money_field(e, "amount"),
        "applies_to": ym_field(e, "applies_to", allow_blank=True),
        "method": f("method"), "reference": f("reference"), "notes": f("notes"),
    }
    if data["kind"] not in KIND_BY_KEY:
        data["kind"] = "rent"
    if data["amount_cents"] == 0:
        e["amount"] = "Enter an amount other than zero."
    if data["lease_id"]:
        pid = scalar("SELECT u.property_id FROM leases l JOIN units u ON u.id = l.unit_id WHERE l.id = ?",
                     (data["lease_id"],))
        if pid is None:
            e["lease_id"] = "That tenant no longer exists."
        else:
            data["property_id"] = pid
    if not data["property_id"] or not scalar("SELECT 1 FROM properties WHERE id = ?", (data["property_id"],)):
        e["property_id"] = "Pick the tenant, or the property this money is for."
    if data["kind"] in RENT_KINDS:
        if not data["lease_id"]:
            e["lease_id"] = "Rent and Section 8 payments need a tenant so the rent roll can match them."
        if not data["applies_to"] and data["date"]:
            data["applies_to"] = ym_of(data["date"])
    else:
        data["applies_to"] = data["applies_to"] if data["kind"] == "late_fee" else None
    return data, e


def _payment_ctx(**kw):
    return dict(kinds=PAYMENT_KINDS, methods=PAYMENT_METHODS, leases=lease_options(),
                properties=property_options(), **kw)


@bp.route("/payments")
def payments():
    year = year_arg()
    pid = request.args.get("property", type=int)
    kind = request.args.get("kind", "")
    sql = """SELECT py.*, p.name AS property_name, t.name AS tenant_name FROM payments py
             JOIN properties p ON p.id = py.property_id
             LEFT JOIN leases l ON l.id = py.lease_id LEFT JOIN tenants t ON t.id = l.tenant_id
             WHERE py.date BETWEEN ? AND ?"""
    args = [f"{year}-01-01", f"{year}-12-31"]
    if pid:
        sql += " AND py.property_id = ?"
        args.append(pid)
    if kind in KIND_BY_KEY:
        sql += " AND py.kind = ?"
        args.append(kind)
    rows = query(sql + " ORDER BY py.date DESC, py.id DESC", args)
    groups = {}
    for r in rows:
        groups.setdefault(r["date"][:7], []).append(r)
    income = sum(r["amount_cents"] for r in rows if r["kind"] in INCOME_KINDS)
    held = sum(r["amount_cents"] for r in rows if r["kind"] == "deposit")
    return render_template("payments/index.html", groups=groups, year=year, years=years_with_data(),
                           income=income, held=held, count=len(rows), properties=property_options(True),
                           pid=pid, kind=kind, kinds=PAYMENT_KINDS)


@bp.route("/payments/new", methods=["GET", "POST"])
def payment_new():
    if not scalar("SELECT COUNT(*) FROM properties"):
        flash("Add a property first.", "error")
        return redirect(url_for("properties.new"))
    if request.method == "POST":
        data, e = _parse_payment()
        if not e:
            execute(f"INSERT INTO payments ({','.join(PAYMENT_COLS)}) VALUES ({','.join('?' * len(PAYMENT_COLS))})",
                    [data[k] for k in PAYMENT_COLS])
            who = scalar("SELECT t.name FROM leases l JOIN tenants t ON t.id = l.tenant_id WHERE l.id = ?",
                         (data["lease_id"],)) if data["lease_id"] else None
            flash(f"Recorded {KIND_BY_KEY[data['kind']]['label'].lower()}{' from ' + who if who else ''}.", "ok")
            back = request.form.get("next", "")
            if request.form.get("again"):
                return redirect(url_for("money.payment_new", kind=data["kind"], date=data["date"],
                                        method=data["method"]))
            return redirect(back if back.startswith("/") and not back.startswith("//") else url_for("money.payments"))
        return render_template("payments/form.html", form=request.form, errors=e, **_payment_ctx()), 400

    today = local_today()
    lease_id = request.args.get("lease_id", type=int)
    kind = request.args.get("kind", "rent")
    form = {"date": request.args.get("date") or today.isoformat(), "kind": kind,
            "lease_id": lease_id or "", "applies_to": request.args.get("applies_to") or ym_of(today),
            "method": request.args.get("method", ""), "property_id": request.args.get("property_id", ""),
            "next": request.args.get("next", "")}
    if lease_id:
        l = query("SELECT * FROM leases WHERE id = ?", (lease_id,), one=True)
        if l:
            if kind == "hap":
                amount = l["hap_cents"]
            elif kind == "rent":
                amount = l["rent_cents"] - (l["hap_cents"] if l["section8"] else 0)
            else:
                amount = None
            if request.args.get("amount"):
                form["amount"] = request.args["amount"]
            elif amount:
                form["amount"] = cents_plain(amount)
    return render_template("payments/form.html", form=form, errors={}, **_payment_ctx())


@bp.route("/payments/<int:pay_id>/edit", methods=["GET", "POST"])
def payment_edit(pay_id):
    row = get_or_404("SELECT * FROM payments WHERE id = ?", (pay_id,))
    if request.method == "POST":
        data, e = _parse_payment()
        if not e:
            execute(f"UPDATE payments SET {', '.join(k + ' = ?' for k in PAYMENT_COLS)} WHERE id = ?",
                    [data[k] for k in PAYMENT_COLS] + [pay_id])
            flash("Saved.", "ok")
            return redirect(url_for("money.payments", year=data["date"][:4]))
        return render_template("payments/form.html", form=request.form, errors=e, row=row, **_payment_ctx()), 400
    form = dict(row)
    form["amount"] = cents_plain(row["amount_cents"])
    return render_template("payments/form.html", form=form, errors={}, row=row, **_payment_ctx())


@bp.route("/payments/<int:pay_id>/delete", methods=["POST"])
def payment_delete(pay_id):
    row = get_or_404("SELECT * FROM payments WHERE id = ?", (pay_id,))
    execute("DELETE FROM payments WHERE id = ?", (pay_id,))
    flash("Payment deleted.", "ok")
    return redirect(url_for("money.payments", year=row["date"][:4]))


# ---------- expenses ----------

EXPENSE_COLS = ["date", "property_id", "category", "vendor", "contact_id", "maintenance_id", "amount_cents",
                "method", "reference", "notes"]


def _parse_expense():
    e = FormErrors()
    data = {
        "date": date_field(e, "date"),
        "property_id": id_field("property_id"),
        "category": f("category"),
        "vendor": f("vendor"),
        "amount_cents": money_field(e, "amount"),
        "maintenance_id": id_field("maintenance_id"),
        "method": f("method"), "reference": f("reference"), "notes": f("notes"),
    }
    if data["category"] not in CATEGORY_BY_KEY:
        e["category"] = "Pick a category so it lands on the right Schedule E line."
    if data["amount_cents"] == 0:
        e["amount"] = "Enter an amount other than zero."
    if data["property_id"] and not scalar("SELECT 1 FROM properties WHERE id = ?", (data["property_id"],)):
        data["property_id"] = None
    data["contact_id"] = scalar("SELECT id FROM contacts WHERE name = ? COLLATE NOCASE", (data["vendor"],)) \
        if data["vendor"] else None
    return data, e


def _expense_ctx(**kw):
    return dict(categories=EXPENSE_CATEGORIES, methods=PAYMENT_METHODS, properties=property_options(),
                vendors=contact_names(), **kw)


@bp.route("/expenses")
def expenses():
    year = year_arg()
    pid = request.args.get("property", "")
    cat = request.args.get("category", "")
    sql = """SELECT e.*, p.name AS property_name,
                    (SELECT COUNT(*) FROM files fl WHERE fl.entity_type = 'expense' AND fl.entity_id = e.id) AS n_files
             FROM expenses e LEFT JOIN properties p ON p.id = e.property_id WHERE e.date BETWEEN ? AND ?"""
    args = [f"{year}-01-01", f"{year}-12-31"]
    if pid == "shared":
        sql += " AND e.property_id IS NULL"
    elif pid.isdigit():
        sql += " AND e.property_id = ?"
        args.append(int(pid))
    if cat in CATEGORY_BY_KEY:
        sql += " AND e.category = ?"
        args.append(cat)
    rows = query(sql + " ORDER BY e.date DESC, e.id DESC", args)
    groups = {}
    for r in rows:
        groups.setdefault(r["date"][:7], []).append(r)
    deductible = sum(r["amount_cents"] for r in rows if CATEGORY_BY_KEY.get(r["category"], {}).get("line"))
    other = sum(r["amount_cents"] for r in rows) - deductible
    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount_cents"]
    return render_template("expenses/index.html", groups=groups, year=year, years=years_with_data(),
                           deductible=deductible, other=other, count=len(rows), by_cat=by_cat,
                           properties=property_options(True), pid=pid, cat=cat, categories=EXPENSE_CATEGORIES,
                           cat_by_key=CATEGORY_BY_KEY)


def _attach_receipt(expense_id):
    file = request.files.get("receipt")
    if file and file.filename:
        try:
            save_upload(file, "expense", expense_id)
        except ValueError as err:
            flash(f"Expense saved, but the receipt wasn't: {err}", "error")


@bp.route("/expenses/new", methods=["GET", "POST"])
def expense_new():
    if request.method == "POST":
        data, e = _parse_expense()
        if not e:
            eid = execute(f"INSERT INTO expenses ({','.join(EXPENSE_COLS)}) "
                          f"VALUES ({','.join('?' * len(EXPENSE_COLS))})", [data[k] for k in EXPENSE_COLS])
            _attach_receipt(eid)
            flash(f"Logged {CATEGORY_BY_KEY[data['category']]['label'].lower()} expense.", "ok")
            if request.form.get("again"):
                return redirect(url_for("money.expense_new", date=data["date"], property_id=data["property_id"] or ""))
            back = request.form.get("next", "")
            return redirect(back if back.startswith("/") and not back.startswith("//") else url_for("money.expenses"))
        return render_template("expenses/form.html", form=request.form, errors=e, **_expense_ctx()), 400
    form = {"date": request.args.get("date") or local_today().isoformat(),
            "property_id": request.args.get("property_id", ""), "category": request.args.get("category", ""),
            "vendor": request.args.get("vendor", ""), "maintenance_id": request.args.get("maintenance_id", ""),
            "notes": request.args.get("notes", ""), "next": request.args.get("next", "")}
    return render_template("expenses/form.html", form=form, errors={}, **_expense_ctx())


@bp.route("/expenses/<int:eid>/edit", methods=["GET", "POST"])
def expense_edit(eid):
    row = get_or_404("SELECT * FROM expenses WHERE id = ?", (eid,))
    files = query("SELECT * FROM files WHERE entity_type = 'expense' AND entity_id = ?", (eid,))
    if request.method == "POST":
        data, e = _parse_expense()
        if not e:
            execute(f"UPDATE expenses SET {', '.join(k + ' = ?' for k in EXPENSE_COLS)} WHERE id = ?",
                    [data[k] for k in EXPENSE_COLS] + [eid])
            _attach_receipt(eid)
            flash("Saved.", "ok")
            return redirect(url_for("money.expenses", year=data["date"][:4]))
        return render_template("expenses/form.html", form=request.form, errors=e, row=row, files=files,
                               **_expense_ctx()), 400
    form = dict(row)
    form["amount"] = cents_plain(row["amount_cents"])
    return render_template("expenses/form.html", form=form, errors={}, row=row, files=files, **_expense_ctx())


@bp.route("/expenses/<int:eid>/delete", methods=["POST"])
def expense_delete(eid):
    row = get_or_404("SELECT * FROM expenses WHERE id = ?", (eid,))
    for fl in query("SELECT * FROM files WHERE entity_type = 'expense' AND entity_id = ?", (eid,)):
        delete_stored(fl["stored_name"])
    conn = get_db()
    conn.execute("DELETE FROM files WHERE entity_type = 'expense' AND entity_id = ?", (eid,))
    conn.execute("DELETE FROM expenses WHERE id = ?", (eid,))
    conn.commit()
    flash("Expense deleted.", "ok")
    return redirect(url_for("money.expenses", year=row["date"][:4]))


@bp.route("/expenses/mortgage", methods=["GET", "POST"])
def mortgage():
    """One mortgage payment -> separate principal / interest / escrow rows."""
    props = property_options()
    if request.method == "POST":
        e = FormErrors()
        date = date_field(e, "date")
        pid = id_field("property_id")
        parts = {k: money_field(e, k, allow_blank=True) or 0 for k in ("interest", "principal", "escrow")}
        lender = f("vendor")
        if not pid:
            e["property_id"] = "Pick the property this mortgage is on."
        if not any(parts.values()):
            e["interest"] = "Enter at least the interest."
        if not e:
            cats = {"interest": "mortgage_interest", "principal": "mortgage_principal", "escrow": "escrow"}
            conn = get_db()
            for part, cents in parts.items():
                if cents:
                    conn.execute("INSERT INTO expenses (date, property_id, category, vendor, amount_cents, method, notes) "
                                 "VALUES (?,?,?,?,?,?,?)",
                                 (date, pid, cats[part], lender, cents, f("method"), "Mortgage payment"))
            conn.commit()
            execute("UPDATE properties SET mortgage_lender = ? WHERE id = ? AND mortgage_lender = ''", (lender, pid))
            flash(f"Logged mortgage payment of ${sum(parts.values()) / 100:,.2f}.", "ok")
            return redirect(url_for("money.expenses"))
        return render_template("expenses/mortgage.html", form=request.form, errors=e, properties=props,
                               methods=PAYMENT_METHODS), 400
    pid = request.args.get("property_id", type=int)
    lender = scalar("SELECT mortgage_lender FROM properties WHERE id = ?", (pid,)) if pid else ""
    last = query("""SELECT category, amount_cents FROM expenses WHERE property_id = ? AND notes = 'Mortgage payment'
                    AND date = (SELECT MAX(date) FROM expenses WHERE property_id = ? AND notes = 'Mortgage payment')""",
                 (pid, pid)) if pid else []
    form = {"date": local_today().isoformat(), "property_id": pid or "", "vendor": lender or ""}
    for r in last:
        key = {"mortgage_interest": "interest", "mortgage_principal": "principal", "escrow": "escrow"}.get(r["category"])
        if key:
            form[key] = cents_plain(r["amount_cents"])
    return render_template("expenses/mortgage.html", form=form, errors={}, properties=props,
                           methods=PAYMENT_METHODS)
