"""PropFlow: a private rent, expense and Schedule E tracker for a small rental portfolio."""
import os
from datetime import timedelta

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app(test_config=None):
    app = Flask(__name__)
    root = os.path.dirname(app.root_path)
    data_dir = os.environ.get("PROPFLOW_DATA") or os.path.join(root, "data")
    app.config.update(
        SECRET_KEY=os.environ.get("PROPFLOW_SECRET_KEY", "dev-only-change-me"),
        DATA_DIR=data_dir,
        DATABASE=os.path.join(data_dir, "propflow.db"),
        UPLOAD_DIR=os.path.join(data_dir, "uploads"),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("PROPFLOW_SECURE_COOKIES", "0") == "1",
        CSRF_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    from . import auth, db
    from .filters import register as register_filters
    db.init_app(app)
    auth.init_app(app)
    register_filters(app)

    from .views import crm, files, imports, main, money, properties, reports, tenants
    for mod in (main, properties, tenants, money, reports, crm, files, imports):
        app.register_blueprint(mod.bp)

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="That page or record doesn't exist."), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, message=getattr(e, "description", "Bad request.")), 400

    @app.errorhandler(413)
    def too_big(_e):
        return render_template("error.html", code=413, message="That file is over 25 MB. Try a smaller photo or PDF."), 413

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    return app
