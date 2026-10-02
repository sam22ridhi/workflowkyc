"""Karyakarta backend: minimal document pipeline (PAN first).

Endpoints
  POST /documents/upload              save file + metadata, then ping n8n (if configured)
  POST /documents/{doc_id}/extract    Sarvam extract -> rule checks -> save -> return   (n8n calls this)
  GET  /documents/{doc_id}            read back the stored result
  GET  /health
"""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import sarvam_client
from app.schemas import SCHEMAS
from app.validators import check_pan, summarise

load_dotenv()

BASE = Path(__file__).resolve().parent.parent
STORAGE = BASE / "storage"
STORAGE.mkdir(exist_ok=True)
DB_PATH = BASE / "karyakarta.db"
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "")  # e.g. http://localhost:5678/webhook/document-uploaded

app = FastAPI(title="Karyakarta backend")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


# ---------- tiny SQLite layer (Cognee comes later) ----------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


with db() as conn:
    conn.execute("""CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY, case_id TEXT, doc_type TEXT, filename TEXT, path TEXT,
        declared_entity_type TEXT, declared_name TEXT,
        status TEXT, fields_json TEXT, checks_json TEXT, raw_json TEXT,
        sarvam_job_id TEXT, created_at TEXT, updated_at TEXT)""")


def now():
    return datetime.now(timezone.utc).isoformat()


# ---------- helpers ----------
def pick_fields(raw: dict, schema: dict) -> tuple[dict, dict]:
    """Find the extracted fields (and per-field confidence) inside Sarvam's results.

    Sarvam returns {"result": ..., "annotations": ...}. The exact nesting can differ by
    version/number of files, so we search for the first dict that contains schema keys.
    Print raw once (scripts/test_sarvam_pan.py) and simplify this when you know the shape.
    """
    keys = set(schema["properties"])

    def find(node):
        if isinstance(node, dict):
            if keys & set(node):
                return node
            for v in node.values():
                hit = find(v)
                if hit is not None:
                    return hit
        elif isinstance(node, list):
            for v in node:
                hit = find(v)
                if hit is not None:
                    return hit
        return None

    fields = find(raw.get("result", raw)) or {}
    ann = find(raw.get("annotations", {})) or {}
    confidence = {}
    for k in keys:
        a = ann.get(k)
        if isinstance(a, dict) and "confidence" in a:
            confidence[k] = a["confidence"]
    return {k: fields.get(k) for k in keys}, confidence


# ---------- routes ----------
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/documents/upload")
def upload(file: UploadFile = File(...), doc_type: str = Form("pan"), case_id: str = Form("demo-case"),
           declared_entity_type: str = Form(""), declared_name: str = Form("")):
    if doc_type not in SCHEMAS:
        raise HTTPException(400, f"Unknown doc_type '{doc_type}'. Known: {list(SCHEMAS)}")
    doc_id = uuid.uuid4().hex[:12]
    dest = STORAGE / f"{doc_id}_{Path(file.filename).name}"
    dest.write_bytes(file.file.read())

    with db() as conn:
        conn.execute("INSERT INTO documents (id, case_id, doc_type, filename, path, declared_entity_type,"
                     " declared_name, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (doc_id, case_id, doc_type, file.filename, str(dest), declared_entity_type,
                      declared_name, "received", now(), now()))

    triggered = False
    if N8N_WEBHOOK_URL:
        try:
            httpx.post(N8N_WEBHOOK_URL, json={"doc_id": doc_id, "doc_type": doc_type, "case_id": case_id},
                       timeout=5)
            triggered = True
        except httpx.HTTPError as e:
            print("n8n webhook failed:", e)
    return {"doc_id": doc_id, "status": "received", "n8n_triggered": triggered}


@app.post("/documents/{doc_id}/extract")
def extract(doc_id: str):
    # plain `def` (not async) so FastAPI runs this blocking call in a worker thread
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "document not found")

    schema = SCHEMAS[row["doc_type"]]
    with db() as conn:
        conn.execute("UPDATE documents SET status=?, updated_at=? WHERE id=?", ("extracting", now(), doc_id))

    try:
        out = sarvam_client.extract(row["path"], schema)
    except Exception as e:  # keep the error visible to n8n and the UI
        with db() as conn:
            conn.execute("UPDATE documents SET status=?, updated_at=? WHERE id=?", ("error", now(), doc_id))
        raise HTTPException(502, f"Sarvam extraction failed: {e}")

    fields, confidence = pick_fields(out["raw"], schema)
    checks = check_pan(fields, row["declared_entity_type"] or None, row["declared_name"] or None) \
        if row["doc_type"] == "pan" else []
    status = summarise(checks)

    with db() as conn:
        conn.execute("UPDATE documents SET status=?, fields_json=?, checks_json=?, raw_json=?, sarvam_job_id=?,"
                     " updated_at=? WHERE id=?",
                     (status, json.dumps(fields), json.dumps(checks), json.dumps(out["raw"], default=str),
                      out["job_id"], now(), doc_id))

    return {"doc_id": doc_id, "doc_type": row["doc_type"], "status": status,
            "checks_passed": status == "verified", "fields": fields, "confidence": confidence,
            "checks": checks, "sarvam_job_id": out["job_id"], "seconds": out["seconds"]}


@app.get("/documents/{doc_id}")
def get_document(doc_id: str):
    with db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "document not found")
    d = dict(row)
    for k in ("fields_json", "checks_json"):
        d[k.replace("_json", "")] = json.loads(d.pop(k)) if d.get(k) else None
    d.pop("raw_json", None)
    return d
