import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

PASSWORD = "correct-horse-1"


@pytest.fixture
def app(tmp_path):
    os.environ["PROPFLOW_DATA"] = str(tmp_path)
    app = create_app({"TESTING": True, "CSRF_ENABLED": False, "SECRET_KEY": "test"})
    with app.app_context():
        from app.auth import set_password
        set_password(PASSWORD)
    yield app
    os.environ.pop("PROPFLOW_DATA", None)


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": PASSWORD})
    return c


@pytest.fixture
def setup_rental(client, app):
    """One duplex: Unit A regular tenant at $1,000, Unit B Section 8 at $900 with $700 HAP."""
    client.post("/properties/new", data={"name": "Elm Duplex", "address": "45 Elm Ave", "city": "Hammond",
                                         "state": "IN", "unit_count": "2", "purchase_date": "2020-01-15",
                                         "purchase_price": "150,000", "land_value": "40000"})
    client.post("/tenants/new", data={"name": "Ann Able", "unit_id": "1", "rent": "1000", "start_date": "2025-06-01",
                                      "due_day": "1", "grace_days": "5", "ledger_start": "2026-01"})
    client.post("/tenants/new", data={"name": "Bo Baker", "unit_id": "2", "rent": "900", "start_date": "2025-06-01",
                                      "section8": "1", "hap": "700", "due_day": "1", "grace_days": "5",
                                      "ledger_start": "2026-01"})
    return app
