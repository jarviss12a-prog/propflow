"""Single-owner login, CSRF protection and a simple lockout on failed logins."""
import secrets
import time

from flask import (Blueprint, abort, flash, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_setting, set_setting

bp = Blueprint("auth", __name__)

OPEN_ENDPOINTS = {"auth.login", "auth.setup", "static", "main.health"}
_failures = {}  # ip -> [timestamps]
MAX_FAILURES, WINDOW = 5, 15 * 60


def password_is_set():
    return bool(get_setting("password_hash"))


def set_password(raw):
    if len(raw) < 8:
        raise ValueError("Use at least 8 characters.")
    set_setting("password_hash", generate_password_hash(raw))


def _locked(ip):
    now = time.time()
    recent = [t for t in _failures.get(ip, []) if now - t < WINDOW]
    _failures[ip] = recent
    return len(recent) >= MAX_FAILURES


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not password_is_set():
        return redirect(url_for("auth.setup"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if _locked(ip):
            flash("Too many wrong passwords. Wait 15 minutes and try again.", "error")
            return render_template("login.html"), 429
        if check_password_hash(get_setting("password_hash"), request.form.get("password", "")):
            _failures.pop(ip, None)
            session.clear()
            session.permanent = True
            session["user"] = "owner"
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("main.dashboard"))
        _failures.setdefault(ip, []).append(time.time())
        time.sleep(0.5)
        flash("That password didn't match.", "error")
    return render_template("login.html")


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First run only: choose the owner password. Disabled once one exists."""
    if password_is_set():
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        pw, again = request.form.get("password", ""), request.form.get("confirm", "")
        if pw != again:
            flash("The two passwords don't match.", "error")
        else:
            try:
                set_password(pw)
            except ValueError as e:
                flash(str(e), "error")
            else:
                session.clear()
                session.permanent = True
                session["user"] = "owner"
                flash("Password saved. You're signed in.", "ok")
                return redirect(url_for("main.dashboard"))
    return render_template("setup.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/settings/password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        if not check_password_hash(get_setting("password_hash"), request.form.get("current", "")):
            flash("Your current password didn't match.", "error")
        elif request.form.get("password") != request.form.get("confirm"):
            flash("The two new passwords don't match.", "error")
        else:
            try:
                set_password(request.form.get("password", ""))
            except ValueError as e:
                flash(str(e), "error")
            else:
                flash("Password changed.", "ok")
                return redirect(url_for("main.more"))
    return render_template("password.html")


def init_app(app):
    app.register_blueprint(bp)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def guard():
        if request.method == "POST" and app.config.get("CSRF_ENABLED", True):
            sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
            if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
                abort(400, "Form expired. Go back, refresh the page and try again.")
        if request.endpoint in OPEN_ENDPOINTS or request.endpoint is None:
            return None
        if session.get("user") != "owner":
            if not password_is_set():
                return redirect(url_for("auth.setup"))
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return None
