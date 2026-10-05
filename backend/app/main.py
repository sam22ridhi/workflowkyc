"""KARYAKARTA API - one backend for the frontend, n8n, Sarvam Document Intelligence and Cognee."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app import config
from app.db import engine, init_db
from app.finops import ledger as finops_ledger
from app.routes import cases, cpv, documents, memory, settlements
from app.seed_cases import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with Session(engine) as s:
        seed_if_empty(s)
        if config.FINOPS_SEED_DEMO:
            finops_ledger.ensure_demo_merchant(s)
    yield


app = FastAPI(title="KARYAKARTA API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(cases.router)
app.include_router(settlements.router)
app.include_router(documents.router)
app.include_router(memory.router)
app.include_router(cpv.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": config.DEMO_MODE, "memory_mode": config.COGNEE_MODE,
            "n8n_configured": bool(config.N8N_WEBHOOK_URL)}
