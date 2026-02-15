from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth
from app.api.v1.endpoints import captures
from app.api.v1.endpoints import catalog
from app.api.v1.endpoints import internal
from app.api.v1.endpoints import media
from app.api.v1.endpoints import products
from app.api.v1.endpoints import profiles
from app.api.v1.endpoints import stream

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(captures.router, tags=["captures"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(profiles.router, tags=["profiles"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(media.router, tags=["media"])
api_router.include_router(internal.router, tags=["internal"])
api_router.include_router(stream.router, tags=["stream"])