import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from . import db
from .explainer import explain_breaks
from .generator import generate
from .matcher import ParseError, parse_trades, reconcile
from .report import run_to_csv

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def read_upload(upload, label):
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{label} is larger than 5 MB")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail=f"{label} must be UTF-8 text")


def create_app(db_path=None, explainer=explain_breaks):
    path = db_path or os.environ.get("RECON_DB", "recon.db")
    db.init(path)
    app = FastAPI(title="Trade Reconciliation Tool")

    def finish(result):
        mode = explainer(result.breaks)
        return db.get_run(path, db.save_run(path, result, mode))

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/reconcile")
    def run_reconciliation(ledger: UploadFile = File(...), custodian: UploadFile = File(...)):
        ledger_text = read_upload(ledger, "Ledger file")
        custodian_text = read_upload(custodian, "Custodian file")
        try:
            result = reconcile(
                parse_trades(ledger_text, "ledger"),
                parse_trades(custodian_text, "custodian"),
            )
        except ParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return finish(result)

    @app.post("/api/demo")
    def run_demo(seed: int = 7):
        ledger, custodian = generate(count=200, seed=seed)
        result = reconcile(
            {t.trade_id: t for t in ledger},
            {t.trade_id: t for t in custodian},
        )
        return finish(result)

    @app.get("/api/runs")
    def runs():
        return db.list_runs(path)

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: int):
        run = db.get_run(path, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.get("/api/runs/{run_id}/export.csv")
    def export_run(run_id: int):
        run = db.get_run(path, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return Response(
            run_to_csv(run),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="reconciliation-run-{run_id}.csv"'},
        )

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
