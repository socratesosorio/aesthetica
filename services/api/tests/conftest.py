from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


@pytest.fixture()
def db_session(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sample_image_path(tmp_path: Path) -> Path:
    p = tmp_path / "capture.jpg"
    Image.new("RGB", (800, 1000), color=(170, 160, 150)).save(p, "JPEG")
    return p


@pytest.fixture(autouse=True)
def configure_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", str(uploads))
