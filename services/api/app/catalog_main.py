from __future__ import annotations

from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from app.api.v1.endpoints.catalog import router as catalog_router
from app.db.session import engine

app = FastAPI(title="Aesthetica Catalog API", version="0.1.0")

v1 = APIRouter(prefix="/v1")
v1.include_router(catalog_router, tags=["catalog"])
app.include_router(v1)


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
    return {"ready": db_ok, "db": db_ok}
