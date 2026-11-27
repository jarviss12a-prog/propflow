"""Gunicorn entry point: gunicorn wsgi:app"""
import os

from dotenv_lite import load_env

load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from app import create_app  # noqa: E402

app = create_app()
if app.config["SECRET_KEY"] == "dev-only-change-me":
    app.logger.warning("PROPFLOW_SECRET_KEY is not set in .env; logins use an insecure default key.")

if __name__ == "__main__":  # python wsgi.py for local testing
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8050")), debug=True)
