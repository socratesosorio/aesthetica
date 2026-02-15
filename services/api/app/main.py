from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.middleware.request_context import RequestContextMiddleware
from ml_core.retrieval import get_catalog

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Aesthetica API", version="0.1.0")
app.add_middleware(RequestContextMiddleware)
cors_origins = {
    settings.base_dashboard_url.rstrip("/"),
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
extra_origins = [
    origin.strip().rstrip("/")
    for origin in settings.cors_extra_origins.split(",")
    if origin.strip()
]
cors_origins.update(extra_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.on_event("startup")
def startup() -> None:
    get_catalog().load()
    logger.info("startup_complete")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "ready": db_ok,
        "db": db_ok,
        "faiss_loaded": get_catalog().is_ready(),
    }
