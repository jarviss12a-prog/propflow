"""Contacts (vendors, lenders, housing authority) and the maintenance log."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..constants import CONTACT_ROLES, MAINTENANCE_STATUSES
from ..db import execute, query, scalar
from ..utils import local_today
from .common import FormErrors, date_field, f, get_or_404, id_field, property_options

bp = Blueprint("crm", __name__)


# ---------- contacts ----------

def _parse_contact():
    e = FormErrors()
    data = {"name": f("name"), "company": f("company"), "role": f("role", "Other"), "phone": f("phone"),
            "email": f("email"), "notes": f("notes")}
    if not data["name"]:
        e["name"] = "Enter a name (a person or a company)."
    if data["role"] not in CONTACT_ROLES:
        data["role"] = "Other"
    return data, e


@bp.route("/contacts")
def contacts():
    q = request.args.get("q", "").strip()
    sql = """SELECT c.*, (SELECT COALESCE(SUM(amount_cents),0) FROM expenses e
                          WHERE e.contact_id = c.id AND substr(e.date,1,4) = ?) AS spent_year
             FROM contacts c"""
    args = [str(local_today().year)]
    if q:
        sql += " WHERE c.name LIKE ? OR c.company LIKE ? OR c.role LIKE ? OR c.notes LIKE ?"
        args += [f"%{q}%"] * 4
    rows = query(sql + " ORDER BY c.role, c.name", args)
    groups = {}
    for r in rows:
        groups.setdefault(r["role"], []).append(r)
    return render_template("contacts/index.html", groups=groups, q=q, count=len(rows), year=local_today().year)


@bp.route("/contacts/new", methods=["GET", "POST"])
def contact_new():
    if request.method == "POST":
        data, e = _parse_contact()
        if not e:
            execute("INSERT INTO contacts (name, company, role, phone, email, notes) VALUES (?,?,?,?,?,?)",
                    [data[k] for k in ("name", "company", "role", "phone", "email", "notes")])
            flash(f"Added {data['name']}.", "ok")
            return redirect(url_for("crm.contacts"))
        return render_template("contacts/form.html", form=request.form, errors=e, roles=CONTACT_ROLES), 400
    return render_template("contacts/form.html", form={"role": request.args.get("role", "")}, errors={},
                           roles=CONTACT_ROLES)


@bp.route("/contacts/<int:cid>/edit", methods=["GET", "POST"])
def contact_edit(cid):
    c = get_or_404("SELECT * FROM contacts WHERE id = ?", (cid,))
    if request.method == "POST":
        data, e = _parse_contact()
        if not e:
            execute("UPDATE contacts SET name=?, company=?, role=?, phone=?, email=?, notes=? WHERE id=?",
                    [data[k] for k in ("name", "company", "role", "phone", "email", "notes")] + [cid])
            flash("Saved.", "ok")
            return redirect(url_for("crm.contacts"))
        return render_template("contacts/form.html", form=request.form, errors=e, c=c, roles=CONTACT_ROLES), 400
    spent = query("""SELECT e.*, p.name AS property_name FROM expenses e LEFT JOIN properties p ON p.id = e.property_id
                     WHERE e.contact_id = ? ORDER BY e.date DESC LIMIT 15""", (cid,))
    return render_template("contacts/form.html", form=dict(c), errors={}, c=c, roles=CONTACT_ROLES, spent=spent)


@bp.route("/contacts/<int:cid>/delete", methods=["POST"])
def contact_delete(cid):
    c = get_or_404("SELECT * FROM contacts WHERE id = ?", (cid,))
    execute("DELETE FROM contacts WHERE id = ?", (cid,))
    flash(f"Deleted {c['name']}. Their past expenses keep the vendor name.", "ok")
    return redirect(url_for("crm.contacts"))


# ---------- maintenance ----------

def _parse_work():
    e = FormErrors()
    data = {
        "property_id": id_field("property_id"), "unit_id": id_field("unit_id"),
        "tenant_id": id_field("tenant_id"), "contact_id": id_field("contact_id"),
        "title": f("title"), "details": f("details"), "status": f("status", "open"),
        "urgent": 1 if request.form.get("urgent") else 0,
        "opened_on": date_field(e, "opened_on"),
        "scheduled_for": date_field(e, "scheduled_for", allow_blank=True),
        "closed_on": date_field(e, "closed_on", allow_blank=True),
    }
    if not data["property_id"] or not scalar("SELECT 1 FROM properties WHERE id = ?", (data["property_id"],)):
        e["property_id"] = "Pick the property."
    if not data["title"]:
        e["title"] = "Say what needs doing, like “Furnace not heating”."
    if data["status"] not in dict(MAINTENANCE_STATUSES):
        data["status"] = "open"
    if data["status"] == "done" and not data["closed_on"]:
        data["closed_on"] = local_today().isoformat()
    if data["status"] != "done":
        data["closed_on"] = None
    return data, e


WORK_COLS = ["property_id", "unit_id", "tenant_id", "contact_id", "title", "details", "status", "urgent",
             "opened_on", "scheduled_for", "closed_on"]


def _work_ctx(**kw):
    tenants = query("SELECT id, name FROM tenants ORDER BY name")
    contacts = query("SELECT id, name, role FROM contacts ORDER BY name")
    return dict(properties=property_options(), tenants=tenants, contacts=contacts, statuses=MAINTENANCE_STATUSES, **kw)


@bp.route("/maintenance")
def maintenance():
    show = request.args.get("show", "open")
    sql = """SELECT m.*, p.name AS property_name, t.name AS tenant_name, c.name AS contact_name, c.phone AS contact_phone,
                    (SELECT COALESCE(SUM(amount_cents),0) FROM expenses e WHERE e.maintenance_id = m.id) AS cost
             FROM maintenance m JOIN properties p ON p.id = m.property_id
             LEFT JOIN tenants t ON t.id = m.tenant_id LEFT JOIN contacts c ON c.id = m.contact_id"""
    if show == "done":
        sql += " WHERE m.status = 'done' ORDER BY m.closed_on DESC LIMIT 200"
    else:
        sql += " WHERE m.status != 'done' ORDER BY m.urgent DESC, m.status, m.opened_on"
    rows = query(sql)
    open_count = scalar("SELECT COUNT(*) FROM maintenance WHERE status != 'done'")
    return render_template("maintenance/index.html", rows=rows, show=show, open_count=open_count,
                           statuses=dict(MAINTENANCE_STATUSES))


@bp.route("/maintenance/new", methods=["GET", "POST"])
def work_new():
    if request.method == "POST":
        data, e = _parse_work()
        if not e:
            wid = execute(f"INSERT INTO maintenance ({','.join(WORK_COLS)}) VALUES ({','.join('?' * len(WORK_COLS))})",
                          [data[k] for k in WORK_COLS])
            flash("Added to the maintenance log.", "ok")
            return redirect(url_for("crm.work_edit", wid=wid))
        return render_template("maintenance/form.html", form=request.form, errors=e, **_work_ctx()), 400
    form = {"opened_on": local_today().isoformat(), "status": "open",
            "property_id": request.args.get("property_id", ""), "tenant_id": request.args.get("tenant_id", "")}
    return render_template("maintenance/form.html", form=form, errors={}, **_work_ctx())


@bp.route("/maintenance/<int:wid>", methods=["GET", "POST"])
def work_edit(wid):
    w = get_or_404("SELECT * FROM maintenance WHERE id = ?", (wid,))
    costs = query("SELECT * FROM expenses WHERE maintenance_id = ? ORDER BY date", (wid,))
    files = query("SELECT * FROM files WHERE entity_type = 'maintenance' AND entity_id = ? ORDER BY uploaded_at DESC",
                  (wid,))
    if request.method == "POST":
        data, e = _parse_work()
        if not e:
            execute(f"UPDATE maintenance SET {', '.join(k + ' = ?' for k in WORK_COLS)} WHERE id = ?",
                    [data[k] for k in WORK_COLS] + [wid])
            flash("Saved.", "ok")
            return redirect(url_for("crm.maintenance"))
        return render_template("maintenance/form.html", form=request.form, errors=e, w=w, costs=costs, files=files,
                               **_work_ctx()), 400
    return render_template("maintenance/form.html", form=dict(w), errors={}, w=w, costs=costs, files=files,
                           **_work_ctx())


@bp.route("/maintenance/<int:wid>/done", methods=["POST"])
def work_done(wid):
    get_or_404("SELECT id FROM maintenance WHERE id = ?", (wid,))
    execute("UPDATE maintenance SET status = 'done', closed_on = ? WHERE id = ?", (local_today().isoformat(), wid))
    flash("Marked done.", "ok")
    return redirect(request.form.get("next") or url_for("crm.maintenance"))


@bp.route("/maintenance/<int:wid>/delete", methods=["POST"])
def work_delete(wid):
    get_or_404("SELECT id FROM maintenance WHERE id = ?", (wid,))
    execute("DELETE FROM maintenance WHERE id = ?", (wid,))
    flash("Deleted from the maintenance log.", "ok")
    return redirect(url_for("crm.maintenance"))
