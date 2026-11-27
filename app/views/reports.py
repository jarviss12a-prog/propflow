"""Tax-time page and the CSV / zip exports for your CPA."""
import csv
import io
import zipfile

from flask import Blueprint, Response, render_template, request

from ..constants import CATEGORY_BY_KEY, KIND_BY_KEY
from ..db import query
from ..ledger import schedule_e
from ..utils import cents_plain, local_today
from .common import year_arg, years_with_data

bp = Blueprint("reports", __name__)


def _split():
    return request.args.get("split", "1") != "0"


@bp.route("/tax")
def tax():
    year = year_arg(local_today().year)
    report = schedule_e(year, split_shared=_split())
    missing_basis = [c["property"]["name"] for c in report["columns"] if c["depreciation"] is None]
    return render_template("tax.html", r=report, year=year, years=years_with_data(), missing_basis=missing_basis)


def _schedule_e_rows(report):
    cols = report["columns"]
    head = ["Line", "Item"] + [c["property"]["name"] for c in cols]
    if not report["split_shared"]:
        head.append("Shared (not split)")
    head.append("Total")
    rows = [head]
    addr = ["", "Address"] + [", ".join(x for x in (c["property"]["address"], c["property"]["city"],
                                                     c["property"]["state"], c["property"]["zip"]) if x)
                              for c in cols]
    unsplit = not report["split_shared"]
    rows.append(addr + ([""] if unsplit else []) + [""])

    def add(line, label, vals, shared=0):
        vals = list(vals) + ([shared] if unsplit else [])
        rows.append([line, label] + [cents_plain(v) for v in vals] + [cents_plain(sum(vals))])

    for line in report["lines"]:
        label = "Depreciation ESTIMATE (confirm with CPA)" if line.get("estimate") else line["label"]
        add(line["line"], label, line["values"], line.get("shared", 0))
    shared_total = report["totals"]["shared"]
    add(20, "Total expenses (lines 5-19)", [c["line20"] for c in cols], shared_total)
    add(21, "Income or (loss): line 3 minus line 20", [c["net_after_depr"] for c in cols], -shared_total)
    rows.append([])
    add("", "Expenses before depreciation", [c["total_expenses"] for c in cols], shared_total)
    add("", "Net before depreciation (cash view)", [c["net_before_depr"] for c in cols], -shared_total)
    rows.append([])
    rows.append(["", "Tracked but not deductible on Schedule E"])
    for nd in report["not_deductible"]:
        add("", nd["label"], nd["values"], nd["shared"])
    rows.append(["", "Security deposits held at year end", cents_plain(report["deposits_held"])])
    return rows


def _payments_rows(year):
    rows = [["Date", "Property", "Tenant", "Type", "Counts as income", "For month", "Amount", "Method",
             "Reference", "Notes"]]
    for r in query("""SELECT py.*, p.name AS property_name, t.name AS tenant_name FROM payments py
                      JOIN properties p ON p.id = py.property_id
                      LEFT JOIN leases l ON l.id = py.lease_id LEFT JOIN tenants t ON t.id = l.tenant_id
                      WHERE py.date BETWEEN ? AND ? ORDER BY py.date, py.id""", (f"{year}-01-01", f"{year}-12-31")):
        k = KIND_BY_KEY.get(r["kind"], {"label": r["kind"], "income": True})
        rows.append([r["date"], r["property_name"], r["tenant_name"] or "", k["label"], "Yes" if k["income"] else "No",
                     r["applies_to"] or "", cents_plain(r["amount_cents"]), r["method"], r["reference"], r["notes"]])
    return rows


def _expenses_rows(year):
    rows = [["Date", "Property", "Category", "Schedule E line", "Vendor", "Amount", "Method", "Reference",
             "Receipts attached", "Notes"]]
    for r in query("""SELECT e.*, p.name AS property_name,
                             (SELECT COUNT(*) FROM files fl WHERE fl.entity_type='expense' AND fl.entity_id=e.id) AS n
                      FROM expenses e LEFT JOIN properties p ON p.id = e.property_id
                      WHERE e.date BETWEEN ? AND ? ORDER BY e.date, e.id""", (f"{year}-01-01", f"{year}-12-31")):
        c = CATEGORY_BY_KEY.get(r["category"], {"label": r["category"], "line": None})
        rows.append([r["date"], r["property_name"] or "All properties (shared)", c["label"],
                     c["line"] or "Not deductible", r["vendor"], cents_plain(r["amount_cents"]), r["method"],
                     r["reference"], r["n"], r["notes"]])
    return rows


def _csv(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def _download(body, name, mimetype="text/csv"):
    return Response(body, mimetype=mimetype, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@bp.route("/tax/<int:year>/schedule-e.csv")
def schedule_e_csv(year):
    return _download(_csv(_schedule_e_rows(schedule_e(year, _split()))), f"schedule-e-{year}.csv")


@bp.route("/export/<int:year>/payments.csv")
def payments_csv(year):
    return _download(_csv(_payments_rows(year)), f"income-{year}.csv")


@bp.route("/export/<int:year>/expenses.csv")
def expenses_csv(year):
    return _download(_csv(_expenses_rows(year)), f"expenses-{year}.csv")


@bp.route("/export/<int:year>/cpa.zip")
def cpa_zip(year):
    """Everything a CPA asks for: Schedule E summary, income and expense detail, and the receipts."""
    import os
    from flask import current_app
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"schedule-e-{year}.csv", _csv(_schedule_e_rows(schedule_e(year, _split()))))
        z.writestr(f"income-{year}.csv", _csv(_payments_rows(year)))
        z.writestr(f"expenses-{year}.csv", _csv(_expenses_rows(year)))
        receipts = query("""SELECT fl.*, e.date, e.vendor FROM files fl JOIN expenses e ON e.id = fl.entity_id
                            WHERE fl.entity_type = 'expense' AND e.date BETWEEN ? AND ?""",
                         (f"{year}-01-01", f"{year}-12-31"))
        for fl in receipts:
            path = os.path.join(current_app.config["UPLOAD_DIR"], fl["stored_name"])
            if os.path.exists(path):
                vendor = "".join(ch for ch in (fl["vendor"] or "receipt") if ch.isalnum() or ch in " -_")[:40]
                z.write(path, f"receipts/{fl['date']} {vendor} {fl['id']}.{fl['stored_name'].rsplit('.', 1)[-1]}")
    return _download(buf.getvalue(), f"propflow-{year}-for-cpa.zip", "application/zip")
