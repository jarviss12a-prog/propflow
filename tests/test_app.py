import io
import zipfile
from datetime import date

import pytest

from app.db import query
from app.ledger import depreciation_estimate, lease_balance, rent_roll, schedule_e
from app.utils import fmt_money, parse_money, parse_ym


# ---------- helpers ----------

@pytest.mark.parametrize("raw,cents", [("1,250.50", 125050), ("$40", 4000), ("(12.30)", -1230), ("-5", -500),
                                       ("0.005", 1), (" 7 ", 700)])
def test_parse_money(raw, cents):
    assert parse_money(raw) == cents


def test_parse_money_rejects_junk():
    with pytest.raises(ValueError):
        parse_money("abc")


def test_fmt_money():
    assert fmt_money(125050) == "$1,250.50"
    assert fmt_money(-500) == "−$5.00"


def test_parse_ym_variants():
    assert parse_ym("2026-03") == "2026-03"
    assert parse_ym("3/2026") == "2026-03"
    assert parse_ym("Mar 2026") == "2026-03"
    assert parse_ym("2026-03-15") == "2026-03"


# ---------- auth ----------

def test_pages_need_login(app):
    c = app.test_client()
    r = c.get("/tax")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_wrong_password(app):
    c = app.test_client()
    r = c.post("/login", data={"password": "nope"})
    assert b"didn" in r.data
    assert c.get("/").status_code == 302


def test_csrf_enforced(tmp_path, monkeypatch):
    from app import create_app
    monkeypatch.setenv("PROPFLOW_DATA", str(tmp_path))
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    c = app.test_client()
    assert c.post("/setup", data={"password": "abcdefgh", "confirm": "abcdefgh"}).status_code == 400


def test_first_run_setup(tmp_path, monkeypatch):
    from app import create_app
    monkeypatch.setenv("PROPFLOW_DATA", str(tmp_path))
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "CSRF_ENABLED": False})
    c = app.test_client()
    assert "/setup" in c.get("/").headers["Location"]
    c.post("/setup", data={"password": "abcdefgh1", "confirm": "abcdefgh1"})
    assert c.get("/").status_code == 200
    # setup is closed once a password exists
    assert "/login" in app.test_client().get("/setup").headers["Location"]


# ---------- properties, tenants, rent ----------

def test_property_creates_units(setup_rental):
    with setup_rental.app_context():
        assert [u["label"] for u in query("SELECT label FROM units ORDER BY id")] == ["Unit A", "Unit B"]


def test_rent_roll_and_section8(client, setup_rental):
    client.post("/payments/new", data={"lease_id": "1", "kind": "rent", "amount": "1000", "date": "2026-03-02",
                                       "applies_to": "2026-03"})
    client.post("/payments/new", data={"lease_id": "2", "kind": "hap", "amount": "700", "date": "2026-03-01",
                                       "applies_to": "2026-03"})
    with setup_rental.app_context():
        rows = {r["lease"]["tenant_name"]: r for r in rent_roll("2026-03", today=date(2026, 3, 20))}
        assert rows["Ann Able"]["status"] == "paid"
        assert rows["Bo Baker"]["status"] == "partial"  # HAP in, tenant's $200 not yet
        assert rows["Bo Baker"]["short"] == 20000
    client.post("/payments/new", data={"lease_id": "2", "kind": "rent", "amount": "200", "date": "2026-03-05"})
    with setup_rental.app_context():
        rows = {r["lease"]["tenant_name"]: r for r in rent_roll("2026-03", today=date(2026, 3, 20))}
        assert rows["Bo Baker"]["status"] == "paid"


def test_due_then_late(setup_rental):
    with setup_rental.app_context():
        assert rent_roll("2026-04", today=date(2026, 4, 3))[0]["status"] == "due"
        assert rent_roll("2026-04", today=date(2026, 4, 9))[0]["status"] == "late"


def test_balance_counts_from_ledger_start(client, setup_rental):
    client.post("/payments/new", data={"lease_id": "1", "kind": "rent", "amount": "1000", "date": "2026-01-03"})
    with setup_rental.app_context():
        lease = query("SELECT * FROM leases WHERE id = 1", one=True)
        # Jan..Mar charged (3 x $1,000), Jan paid -> owes $2,000 on Mar 10
        assert lease_balance(lease, today=date(2026, 3, 10)) == 200000


def test_move_out_stops_rent(client, setup_rental):
    client.post("/leases/1/move-out", data={"move_out_date": "2026-02-15"})
    with setup_rental.app_context():
        names = [r["lease"]["tenant_name"] for r in rent_roll("2026-03", today=date(2026, 3, 20))]
        assert "Ann Able" not in names


def test_rent_needs_tenant(client, setup_rental):
    r = client.post("/payments/new", data={"property_id": "1", "kind": "rent", "amount": "50", "date": "2026-03-01"})
    assert r.status_code == 400


def test_cannot_delete_property_with_money(client, setup_rental):
    client.post("/payments/new", data={"lease_id": "1", "kind": "rent", "amount": "1000", "date": "2026-01-03"})
    client.post("/properties/1/delete")
    with setup_rental.app_context():
        assert query("SELECT COUNT(*) FROM properties", one=True)[0] == 1


# ---------- taxes ----------

def test_schedule_e_lines_and_deposits(client, setup_rental):
    client.post("/payments/new", data={"lease_id": "1", "kind": "rent", "amount": "1000", "date": "2026-01-03"})
    client.post("/payments/new", data={"lease_id": "1", "kind": "late_fee", "amount": "50", "date": "2026-01-09"})
    client.post("/payments/new", data={"lease_id": "1", "kind": "deposit", "amount": "1000", "date": "2026-01-03"})
    client.post("/expenses/new", data={"property_id": "1", "category": "repairs", "amount": "185", "date": "2026-02-01"})
    client.post("/expenses/new", data={"property_id": "1", "category": "capital_improvement", "amount": "9000",
                                       "date": "2026-02-01"})
    with setup_rental.app_context():
        r = schedule_e(2026)
        col = r["columns"][0]
        assert col["line3"] == 105000  # rent + late fee, not the deposit
        assert col["cats"]["repairs"] == 18500
        assert col["total_expenses"] == 18500  # capital improvement is not expensed
        assert r["deposits_held"] == 100000


def test_shared_expense_split_to_the_penny(client, setup_rental):
    client.post("/properties/new", data={"name": "Oak", "unit_count": "1"})
    client.post("/properties/new", data={"name": "Pine", "unit_count": "1"})
    client.post("/expenses/new", data={"property_id": "", "category": "legal_professional", "amount": "100",
                                       "date": "2026-03-01"})
    with setup_rental.app_context():
        r = schedule_e(2026)
        parts = [c["cats"]["legal_professional"] for c in r["columns"]]
        assert sum(parts) == 10000 and sorted(parts) == [3333, 3333, 3334]
        unsplit = schedule_e(2026, split_shared=False)
        assert unsplit["totals"]["expenses"] == 10000


def test_depreciation_mid_month():
    prop = {"purchase_price_cents": 15000000, "land_value_cents": 4000000, "placed_in_service": None,
            "purchase_date": "2020-01-15"}
    annual = 11000000 / 27.5
    assert depreciation_estimate(prop, 2020) == round(annual * 11.5 / 12)
    assert depreciation_estimate(prop, 2026) == round(annual)
    assert depreciation_estimate(prop, 2019) == 0


def test_mortgage_split(client, setup_rental):
    client.post("/expenses/mortgage", data={"property_id": "1", "date": "2026-03-01", "interest": "410.22",
                                            "principal": "389.78", "escrow": "250", "vendor": "Chase"})
    with setup_rental.app_context():
        rows = {r["category"]: r["amount_cents"] for r in query("SELECT category, amount_cents FROM expenses")}
        assert rows == {"mortgage_interest": 41022, "mortgage_principal": 38978, "escrow": 25000}
        assert schedule_e(2026)["columns"][0]["total_expenses"] == 41022


def test_exports(client, setup_rental):
    client.post("/payments/new", data={"lease_id": "1", "kind": "rent", "amount": "1000", "date": "2026-01-03"})
    data = {"property_id": "1", "category": "repairs", "amount": "185", "date": "2026-02-01",
            "receipt": (io.BytesIO(b"%PDF-1.4 fake"), "plumber.pdf")}
    client.post("/expenses/new", data=data, content_type="multipart/form-data")
    csv = client.get("/tax/2026/schedule-e.csv").data.decode()
    assert "Rents received" in csv and "1000.00" in csv
    z = zipfile.ZipFile(io.BytesIO(client.get("/export/2026/cpa.zip").data))
    names = z.namelist()
    assert "schedule-e-2026.csv" in names and any(n.startswith("receipts/") for n in names)


def test_upload_rejects_scripts(client, setup_rental):
    r = client.post("/files/upload", data={"entity_type": "property", "entity_id": "1", "next": "/properties/1",
                                           "file": (io.BytesIO(b"x"), "evil.html")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert b"can&#39;t be attached" in r.data


# ---------- import ----------

PAYMENTS_CSV = """Date,Tenant,Amount Paid,Type,For Month,Method,Memo
1/3/2026,ann able,"$1,000.00",,2026-01,Zelle,
1/2/2026,Bo Baker,700,section 8,Jan 2026,ACH,HAP
1/5/2026,Nobody Here,5,,,,
"""


def test_import_payments(client, setup_rental):
    r = client.post("/import", data={"kind": "payments", "pasted": PAYMENTS_CSV})
    assert r.status_code == 200 and b"2 ready" in r.data
    token = r.data.decode().split('name="token" value="')[1].split('"')[0]
    client.post("/import/commit", data={"token": token})
    with setup_rental.app_context():
        rows = query("SELECT kind, amount_cents, applies_to, lease_id FROM payments ORDER BY lease_id")
        assert [(x["kind"], x["amount_cents"], x["applies_to"]) for x in rows] == [
            ("rent", 100000, "2026-01"), ("hap", 70000, "2026-01")]
    again = client.post("/import", data={"kind": "payments", "pasted": PAYMENTS_CSV})
    assert b"0 ready" in again.data and b"already in PropFlow" in again.data


def test_import_properties_and_tenants(client):
    client.post("/import/commit", data={"token": _preview(client, "properties",
                "name,address,units\nMaple St,123 Maple,1\nElm Duplex,45 Elm,2\n")})
    client.post("/import/commit", data={"token": _preview(client, "tenants",
                "name,property,unit,lease_start,rent,section8,hap\nJ Doe,Maple St,,2025-08-01,1200,,\n"
                "R Roe,Elm Duplex,Unit B,2024-02-01,1050,yes,850\n")})
    rows = query_all(client, "SELECT t.name, l.rent_cents, l.hap_cents, u.label FROM leases l "
                             "JOIN tenants t ON t.id = l.tenant_id JOIN units u ON u.id = l.unit_id ORDER BY t.name")
    assert rows == [("J Doe", 120000, 0, "Main"), ("R Roe", 105000, 85000, "Unit B")]


def test_import_expense_categories(client, setup_rental):
    token = _preview(client, "expenses", "date,property,category,vendor,amount\n"
                     "2026-01-10,Elm Duplex,plumbing,Joe,185\n2026-01-15,shared,cpa,Smith CPA,450\n"
                     "2026-01-16,Elm Duplex,mystery,X,1\n")
    client.post("/import/commit", data={"token": token})
    rows = query_all(client, "SELECT category, property_id FROM expenses ORDER BY id")
    assert rows == [("repairs", 1), ("legal_professional", None)]


def _preview(client, kind, text):
    r = client.post("/import", data={"kind": kind, "pasted": text})
    return r.data.decode().split('name="token" value="')[1].split('"')[0]


def query_all(client, sql):
    with client.application.app_context():
        return [tuple(r) for r in query(sql)]


def test_every_page_renders(client, setup_rental):
    client.post("/payments/new", data={"lease_id": "1", "kind": "rent", "amount": "1000", "date": "2026-01-03"})
    client.post("/expenses/new", data={"property_id": "1", "category": "repairs", "amount": "185", "date": "2026-02-01"})
    client.post("/contacts/new", data={"name": "Joe's Plumbing", "role": "Plumber"})
    client.post("/maintenance/new", data={"property_id": "1", "title": "Leak", "opened_on": "2026-02-01"})
    for url in ["/", "/rent", "/payments", "/payments/new", "/payments/1/edit", "/expenses", "/expenses/new",
                "/expenses/1/edit", "/expenses/mortgage", "/tax", "/tax?split=0", "/properties", "/properties/1",
                "/properties/1/edit", "/units/1/edit", "/tenants", "/tenants/1", "/tenants/2", "/leases/2/edit",
                "/tenants/1/leases/new", "/contacts", "/contacts/1/edit", "/maintenance", "/maintenance/1",
                "/import", "/more", "/settings/password"]:
        assert client.get(url).status_code == 200, url
