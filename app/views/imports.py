"""Import page: upload a CSV, check the preview, then add the rows."""
import json
import os
import secrets
import time

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for

from .. import importer
from ..constants import EXPENSE_CATEGORIES, PAYMENT_KINDS

bp = Blueprint("imports", __name__)

LABELS = {"properties": "Properties", "tenants": "Tenants and leases", "payments": "Payments (money in)",
          "expenses": "Expenses (money out)"}


def _dir():
    d = os.path.join(current_app.config["DATA_DIR"], "imports")
    os.makedirs(d, exist_ok=True)
    for name in os.listdir(d):  # drop abandoned previews after a day
        p = os.path.join(d, name)
        if time.time() - os.path.getmtime(p) > 86400:
            os.remove(p)
    return d


@bp.route("/import", methods=["GET", "POST"])
def index():
    kind = request.values.get("kind", "payments")
    if kind not in importer.KINDS:
        kind = "payments"
    if request.method == "POST":
        file = request.files.get("file")
        text = request.form.get("pasted", "")
        if file and file.filename:
            raw = file.read()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
        if not text.strip():
            flash("Choose a CSV file or paste rows first.", "error")
            return redirect(url_for("imports.index", kind=kind))
        rows, unknown = importer.read_csv(text, kind)
        if not rows:
            flash("That file had no rows under the header.", "error")
            return redirect(url_for("imports.index", kind=kind))
        items = importer.prepare(kind, rows)
        token = secrets.token_hex(10)
        with open(os.path.join(_dir(), f"{token}.json"), "w") as fh:
            json.dump({"kind": kind, "items": items}, fh)
        return render_template("import_preview.html", kind=kind, label=LABELS[kind], items=items,
                               cols=importer.KINDS[kind], token=token, unknown=unknown,
                               summary=importer.summarize(kind, items))
    return render_template("import.html", kind=kind, labels=LABELS, cols=importer.KINDS[kind],
                           required=importer.REQUIRED[kind], categories=EXPENSE_CATEGORIES, kinds=PAYMENT_KINDS)


@bp.route("/import/commit", methods=["POST"])
def commit():
    token = request.form.get("token", "")
    path = os.path.join(_dir(), f"{token}.json")
    if not token.isalnum() or not os.path.exists(path):
        flash("That preview expired. Upload the file again.", "error")
        return redirect(url_for("imports.index"))
    with open(path) as fh:
        saved = json.load(fh)
    added = importer.commit(saved["kind"], saved["items"], include_dupes=bool(request.form.get("include_dupes")))
    os.remove(path)
    flash(f"Added {added} {LABELS[saved['kind']].split(' ')[0].lower()} row{'s' if added != 1 else ''}.", "ok")
    target = {"properties": "properties.index", "tenants": "tenants.index", "payments": "money.payments",
              "expenses": "money.expenses"}[saved["kind"]]
    return redirect(url_for(target))


@bp.route("/import/template/<kind>.csv")
def template(kind):
    if kind not in importer.KINDS:
        return redirect(url_for("imports.index"))
    return Response(importer.template_csv(kind), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="propflow-{kind}-template.csv"'})
