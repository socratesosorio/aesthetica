from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.product_ingest import ingest_products_csv, rebuild_faiss_from_db
from ml_core.config import CONFIG
from ml_core.retrieval import get_catalog

router = APIRouter(prefix="/internal")


def _authz_dev(token: str | None) -> None:
    if token != "dev":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/reindex-products")
def reindex_products(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _authz_dev((authorization or "").replace("Bearer ", ""))
    ingested = ingest_products_csv(db, CONFIG.product_csv_path)
    stats = rebuild_faiss_from_db(db, CONFIG.faiss_dir)
    get_catalog().load()
    return {"ingested": ingested, "indexed": stats}


@router.post("/recompute-radar")
def recompute_radar(authorization: str | None = Header(default=None)):
    _authz_dev((authorization or "").replace("Bearer ", ""))
    return {"status": "not_implemented_mvp"}
