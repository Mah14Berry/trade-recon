import csv
import io

import pytest
from fastapi.testclient import TestClient

from recon.api import create_app

HEADER = "trade_id,ticker,quantity,price,trade_date,settle_date\n"
LEDGER = HEADER + "T1,AAPL,100,190.00,2026-09-01,2026-09-02\nT2,KO,50,60.00,2026-09-01,2026-09-02\n"
CUSTODIAN = HEADER + "T1,AAPL,90,190.00,2026-09-01,2026-09-02\nT3,KO,50,60.00,2026-09-01,2026-09-02\n"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(db_path=str(tmp_path / "test.db")))


def upload(client, ledger=LEDGER, custodian=CUSTODIAN):
    return client.post(
        "/api/reconcile",
        files={
            "ledger": ("ledger.csv", ledger, "text/csv"),
            "custodian": ("custodian.csv", custodian, "text/csv"),
        },
    )


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_reconcile_returns_summary_and_breaks(client):
    response = upload(client)
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["matched"] == 0
    assert body["summary"]["break_count"] == 3
    assert body["summary"]["by_type"] == {
        "MISSING_IN_CUSTODIAN": 1,
        "MISSING_IN_LEDGER": 1,
        "QUANTITY_MISMATCH": 1,
    }
    assert body["summary"]["explanation_mode"] == "rule_based"
    assert all(item["explanation"] for item in body["breaks"])


def test_reconcile_with_bom_encoded_files(client):
    response = upload(client, ledger="\ufeff" + LEDGER)
    assert response.status_code == 200


def test_bad_file_returns_400_with_reason(client):
    response = upload(client, ledger="trade_id,ticker\nT1,AAPL\n")
    assert response.status_code == 400
    assert "missing columns" in response.json()["detail"]


def test_non_utf8_file_returns_400(client):
    response = client.post(
        "/api/reconcile",
        files={
            "ledger": ("ledger.csv", b"\xff\xfe\x00bad", "text/csv"),
            "custodian": ("custodian.csv", CUSTODIAN, "text/csv"),
        },
    )
    assert response.status_code == 400


def test_missing_upload_returns_422(client):
    response = client.post("/api/reconcile", files={"ledger": ("l.csv", LEDGER, "text/csv")})
    assert response.status_code == 422


def test_runs_are_persisted_and_listed(client):
    run_id = upload(client).json()["id"]
    listing = client.get("/api/runs").json()
    assert listing[0]["id"] == run_id
    assert listing[0]["break_count"] == 3
    assert client.get(f"/api/runs/{run_id}").json()["summary"]["break_count"] == 3


def test_unknown_run_returns_404(client):
    assert client.get("/api/runs/999").status_code == 404
    assert client.get("/api/runs/999/export.csv").status_code == 404


def test_export_csv(client):
    run_id = upload(client).json()["id"]
    response = client.get(f"/api/runs/{run_id}/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("trade_id,break_type")
    assert len(lines) == 4


def test_export_neutralises_spreadsheet_formulas(tmp_path):
    def evil(breaks):
        for item in breaks:
            item.explanation = "=HYPERLINK(\"http://example.com\")"
            item.suggested_action = "+cmd"
        return "llm"

    client = TestClient(create_app(db_path=str(tmp_path / "evil.db"), explainer=evil))
    run_id = upload(client).json()["id"]
    text = client.get(f"/api/runs/{run_id}/export.csv").text
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows
    assert all(row["explanation"].startswith("'=HYPERLINK") for row in rows)
    assert all(row["suggested_action"] == "'+cmd" for row in rows)


def test_demo_run(client):
    body = client.post("/api/demo").json()
    assert body["summary"]["break_count"] == 24
    assert body["summary"]["ledger_count"] == 200


def test_dashboard_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Trade reconciliation" in response.text
