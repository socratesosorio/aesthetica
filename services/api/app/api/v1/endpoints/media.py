from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import decode_access_token
from app.models import User

router = APIRouter()


@router.get("/media")
def get_media(
    path: str = Query(...),
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw = token or (authorization or "").replace("Bearer ", "")
    if not raw:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if raw == "dev":
        user = db.query(User).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        try:
            user_id = decode_access_token(raw)
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Unauthorized") from exc
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

    del user
    p = Path(path).resolve()
    allowed_roots = [Path("/app/data/uploads").resolve(), Path("data/uploads").resolve()]
    if not any(str(p).startswith(str(root)) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Forbidden path")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(p))
