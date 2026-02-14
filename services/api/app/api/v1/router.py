from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, captures, internal, media, products, profiles

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(captures.router, tags=["captures"])
api_router.include_router(profiles.router, tags=["profiles"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(media.router, tags=["media"])
api_router.include_router(internal.router, tags=["internal"])
