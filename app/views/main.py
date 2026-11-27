from datetime import timedelta

from flask import Blueprint, render_template

from ..db import query, scalar
from ..ledger import (LEASE_SELECT, by_property, expense_total, income_total, place_label,
                      rent_roll, rent_roll_summary, year_bounds)
from ..utils import local_today, ym_of

bp = Blueprint("main", __name__)


@bp.route("/health")
def health():
    return {"ok": True}


@bp.route("/")
def dashboard():
    today = local_today()
    ym = ym_of(today)
    if not scalar("SELECT COUNT(*) FROM properties"):
        return render_template("welcome.html")

    roll = rent_roll(ym)
    summary = rent_roll_summary(roll)
    start, end = year_bounds(today.year)
    ytd = {"income": income_total(start, today.isoformat()),
           "expenses": expense_total(start, today.isoformat())}
    ytd["net"] = ytd["income"] - ytd["expenses"]
    props, shared = by_property(start, end)

    soon = (today + timedelta(days=75)).isoformat()
    ending = [dict(r, place=place_label(r)) for r in query(
        LEASE_SELECT + """ WHERE l.move_out_date IS NULL AND l.end_date IS NOT NULL
                           AND l.end_date <= ? AND p.archived = 0 ORDER BY l.end_date""", (soon,))]
    work = query("""SELECT m.*, p.name AS property_name FROM maintenance m
                    JOIN properties p ON p.id = m.property_id
                    WHERE m.status != 'done' ORDER BY m.urgent DESC, m.opened_on LIMIT 6""")
    recent = query("""
        SELECT 'in' AS dir, py.id AS id, py.date AS date, py.amount_cents AS amount_cents, py.kind AS what,
               COALESCE(t.name, '') AS who, p.name AS property_name
        FROM payments py JOIN properties p ON p.id = py.property_id
        LEFT JOIN leases l ON l.id = py.lease_id LEFT JOIN tenants t ON t.id = l.tenant_id
        UNION ALL
        SELECT 'out', e.id, e.date, e.amount_cents, e.category, e.vendor,
               COALESCE(p.name, 'All properties')
        FROM expenses e LEFT JOIN properties p ON p.id = e.property_id
        ORDER BY date DESC, id DESC LIMIT 8""")
    return render_template("dashboard.html", ym=ym, roll=roll, summary=summary, ytd=ytd,
                           props=props, shared=shared, ending=ending, work=work, recent=recent,
                           today=today)


@bp.route("/more")
def more():
    counts = {
        "contacts": scalar("SELECT COUNT(*) FROM contacts"),
        "open_work": scalar("SELECT COUNT(*) FROM maintenance WHERE status != 'done'"),
        "properties": scalar("SELECT COUNT(*) FROM properties WHERE archived = 0"),
    }
    return render_template("more.html", counts=counts)
