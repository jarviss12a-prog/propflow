"""Saving uploaded receipts, leases and photos under DATA_DIR/uploads."""
import os
import secrets

from flask import current_app
from werkzeug.utils import secure_filename

from .constants import ALLOWED_UPLOADS
from .db import execute

ENTITY_TYPES = {"property", "tenant", "expense", "payment", "maintenance", "contact"}


def save_upload(file, entity_type, entity_id):
    """Store one werkzeug FileStorage. Returns the new files.id, or raises ValueError."""
    if entity_type not in ENTITY_TYPES:
        raise ValueError("Unknown attachment type.")
    if not file or not file.filename:
        raise ValueError("Choose a file.")
    original = file.filename
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED_UPLOADS:
        raise ValueError(f"“{original}” can't be attached. Use a PDF, photo, Word, Excel or CSV file.")
    stored = f"{secrets.token_hex(12)}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_DIR"], stored)
    file.save(path)
    size = os.path.getsize(path)
    return execute("INSERT INTO files (entity_type, entity_id, original_name, stored_name, size, content_type) "
                   "VALUES (?,?,?,?,?,?)",
                   (entity_type, entity_id, secure_filename(original) or f"file.{ext}", stored, size,
                    file.mimetype or ""))


def delete_stored(stored_name):
    path = os.path.join(current_app.config["UPLOAD_DIR"], os.path.basename(stored_name))
    if os.path.exists(path):
        os.remove(path)
