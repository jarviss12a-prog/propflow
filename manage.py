#!/usr/bin/env python3
"""PropFlow command line.

  python manage.py set-password              choose or reset the owner password
  python manage.py import payments FILE.csv  preview a CSV, then add it (also: properties, tenants, expenses)
  python manage.py backup [DEST_DIR]         safe copy of the database + uploads
  python manage.py demo                      fill an EMPTY database with made-up sample data
  python manage.py check                     print row counts and the schema version
"""
import getpass
import os
import sqlite3
import sys
import tarfile
from datetime import datetime

from dotenv_lite import load_env

load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app import create_app  # noqa: E402


def cmd_set_password(app, args):
    from app.auth import set_password
    pw = os.environ.get("PROPFLOW_NEW_PASSWORD") or getpass.getpass("New owner password (8+ characters): ")
    if not os.environ.get("PROPFLOW_NEW_PASSWORD") and getpass.getpass("Again: ") != pw:
        sys.exit("Passwords didn't match.")
    with app.app_context():
        try:
            set_password(pw)
        except ValueError as e:
            sys.exit(str(e))
    print("Password saved.")


def cmd_import(app, args):
    from app import importer
    if len(args) < 2 or args[0] not in importer.KINDS:
        sys.exit(f"Usage: manage.py import {{{'|'.join(importer.KINDS)}}} FILE.csv [--yes] [--include-dupes]")
    kind, path = args[0], args[1]
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    with app.app_context():
        rows, unknown = importer.read_csv(text, kind)
        items = importer.prepare(kind, rows)
        if unknown:
            print("Ignored columns:", ", ".join(unknown))
        for it in items:
            state = "ERROR " + it["error"] if it["error"] else ("DUPLICATE" if it["dupe"] else "ok")
            print(f"row {it['n']:>4}  {state:<12}  {' | '.join(it['show'])}")
        s = importer.summarize(kind, items)
        print(f"\n{s['ready']} ready, {s['errors']} errors, {s['dupes']} duplicates"
              + (f", total {s['total']}" if s["total"] else ""))
        if "--yes" not in args:
            if input("Add the ready rows? [y/N] ").strip().lower() != "y":
                print("Nothing added.")
                return
        print(f"Added {importer.commit(kind, items, include_dupes='--include-dupes' in args)} rows.")


def cmd_backup(app, args):
    dest = args[0] if args else os.path.join(app.config["DATA_DIR"], "backups")
    os.makedirs(dest, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    db_copy = os.path.join(dest, f"propflow-{stamp}.db")
    src = sqlite3.connect(app.config["DATABASE"])
    out = sqlite3.connect(db_copy)
    with out:
        src.backup(out)
    src.close()
    out.close()
    archive = os.path.join(dest, f"propflow-{stamp}.tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(db_copy, arcname="propflow.db")
        tar.add(app.config["UPLOAD_DIR"], arcname="uploads")
    os.remove(db_copy)
    keep = int(os.environ.get("PROPFLOW_KEEP_BACKUPS", "30"))
    olds = sorted(f for f in os.listdir(dest) if f.startswith("propflow-") and f.endswith(".tar.gz"))
    for f in olds[:-keep]:
        os.remove(os.path.join(dest, f))
    print(archive)


def cmd_demo(app, args):
    from demo_data import load
    with app.app_context():
        load()
    print("Demo data loaded.")


def cmd_check(app, args):
    with app.app_context():
        from app.db import query
        print("schema version", query("PRAGMA user_version", one=True)[0])
        for t in ("properties", "units", "tenants", "leases", "payments", "expenses", "contacts", "maintenance", "files"):
            print(f"{t:<12} {query(f'SELECT COUNT(*) FROM {t}', one=True)[0]}")
        print("database", app.config["DATABASE"])


COMMANDS = {"set-password": cmd_set_password, "import": cmd_import, "backup": cmd_backup, "demo": cmd_demo,
            "check": cmd_check}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](create_app(), sys.argv[2:])
