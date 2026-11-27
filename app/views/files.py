"""Attachments: receipts, leases, photos. Served only to a signed-in owner."""
from flask import Blueprint, current_app, flash, redirect, request, send_from_directory

from ..db import execute
from ..storage import ENTITY_TYPES, delete_stored, save_upload
from .common import get_or_404

bp = Blueprint("files", __name__)

INLINE = {"pdf", "jpg", "jpeg", "png", "gif", "webp", "txt"}


def _back():
    nxt = request.form.get("next", "")
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else "/"


@bp.route("/files/upload", methods=["POST"])
def upload():
    entity_type = request.form.get("entity_type", "")
    entity_id = request.form.get("entity_id", type=int)
    if entity_type not in ENTITY_TYPES or not entity_id:
        flash("Couldn't tell what to attach that to.", "error")
        return redirect(_back())
    saved = 0
    for file in request.files.getlist("file"):
        try:
            save_upload(file, entity_type, entity_id)
            saved += 1
        except ValueError as e:
            flash(str(e), "error")
    if saved:
        flash(f"Attached {saved} file{'s' if saved != 1 else ''}.", "ok")
    return redirect(_back())


@bp.route("/files/<int:fid>")
def download(fid):
    fl = get_or_404("SELECT * FROM files WHERE id = ?", (fid,))
    ext = fl["stored_name"].rsplit(".", 1)[-1].lower()
    return send_from_directory(current_app.config["UPLOAD_DIR"], fl["stored_name"],
                               as_attachment=ext not in INLINE, download_name=fl["original_name"])


@bp.route("/files/<int:fid>/delete", methods=["POST"])
def delete(fid):
    fl = get_or_404("SELECT * FROM files WHERE id = ?", (fid,))
    delete_stored(fl["stored_name"])
    execute("DELETE FROM files WHERE id = ?", (fid,))
    flash(f"Removed {fl['original_name']}.", "ok")
    return redirect(_back())
