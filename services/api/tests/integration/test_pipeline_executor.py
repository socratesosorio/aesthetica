from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from app.models import Capture, Product, User, UserProfile, UserRadarHistory
from app.services.pipeline_executor import process_capture


@dataclass
class _MockGarment:
    garment_type: str
    embedding: np.ndarray
    attributes: dict
    crop: Image.Image


@dataclass
class _MockResult:
    global_embedding: np.ndarray
    garments: list[_MockGarment]
    global_attributes: dict


class _MockPipeline:
    def __init__(self, catalog) -> None:
        self.catalog = catalog

    def run(self, image: Image.Image) -> _MockResult:
        emb = np.zeros(512, dtype=np.float32)
        emb[0] = 1.0
        garment = _MockGarment(
            garment_type="top",
            embedding=emb,
            attributes={
                "colors": [{"hex": "#000000", "pct": 1.0}],
                "pattern": {"type": "solid", "confidence": 0.9},
                "formality": 60.0,
                "structure": 50.0,
                "minimalism": 55.0,
                "silhouette": "regular",
                "notes": ["mock"],
            },
            crop=Image.new("RGBA", (64, 64), (50, 60, 70, 255)),
        )
        return _MockResult(
            global_embedding=emb,
            garments=[garment],
            global_attributes=garment.attributes,
        )


class _MockCatalog:
    def query(self, category: str, vector: np.ndarray, top_k: int = 30):
        class R:
            def __init__(self, pid: str, sim: float, rank: int):
                self.product_id = pid
                self.similarity = sim
                self.rank = rank

        return [R("p_top_1", 0.95, 1), R("p_top_2", 0.91, 2), R("p_top_3", 0.88, 3)]


class _MockNotifier:
    def __init__(self):
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


class _FailingNotifier:
    def send(self, message: str) -> None:
        raise RuntimeError("notification transient failure")


def test_pipeline_executor_updates_db(monkeypatch, db_session, sample_image_path):
    user = User(email="demo@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    db_session.add_all(
        [
            Product(
                id="p_top_1",
                title="Black Tee",
                brand="A",
                category="top",
                price=50,
                currency="USD",
                image_url="https://example.com/1.jpg",
                product_url="https://example.com/1",
                color_tags=None,
            ),
            Product(
                id="p_top_2",
                title="Budget Tee",
                brand="B",
                category="top",
                price=35,
                currency="USD",
                image_url="https://example.com/2.jpg",
                product_url="https://example.com/2",
                color_tags=None,
            ),
            Product(
                id="p_top_3",
                title="Premium Tee",
                brand="C",
                category="top",
                price=80,
                currency="USD",
                image_url="https://example.com/3.jpg",
                product_url="https://example.com/3",
                color_tags=None,
            ),
        ]
    )

    capture = Capture(user_id=user.id, image_path=str(sample_image_path), status="queued")
    db_session.add(capture)
    db_session.commit()

    monkeypatch.setattr("app.services.pipeline_executor.CapturePipeline", _MockPipeline)
    monkeypatch.setattr("app.services.pipeline_executor.get_catalog", lambda: _MockCatalog())

    class _FakeTaste:
        def update_embedding(self, prev, cur):
            return cur

        def radar_scores(self, emb):
            return {
                "minimal_maximal": 55.0,
                "structured_relaxed": 48.0,
                "neutral_color_forward": 52.0,
                "classic_experimental": 49.0,
                "casual_formal": 51.0,
            }

        def delta(self, old, new):
            return {k: new[k] - (old or {}).get(k, 0.0) for k in new}

    monkeypatch.setattr("app.services.pipeline_executor.TasteProfileEngine", lambda: _FakeTaste())

    notifier = _MockNotifier()
    process_capture(db_session, capture.id, notifier=notifier)

    updated = db_session.query(Capture).filter(Capture.id == capture.id).first()
    assert updated is not None
    assert updated.status == "done"
    assert len(updated.garments) == 1
    assert len(updated.matches) >= 1

    profile = db_session.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    assert profile is not None
    assert profile.radar_vector_json["minimal_maximal"] == 55.0

    history = db_session.query(UserRadarHistory).filter(UserRadarHistory.user_id == user.id).all()
    assert len(history) == 1

    assert len(notifier.messages) == 1
    assert "Top matches" in notifier.messages[0]


def test_pipeline_executor_does_not_raise_on_post_commit_notifier_failure(monkeypatch, db_session, sample_image_path):
    user = User(email="demo2@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    db_session.add_all(
        [
            Product(
                id="p_top_1",
                title="Black Tee",
                brand="A",
                category="top",
                price=50,
                currency="USD",
                image_url="https://example.com/1.jpg",
                product_url="https://example.com/1",
                color_tags=None,
            ),
            Product(
                id="p_top_2",
                title="Budget Tee",
                brand="B",
                category="top",
                price=35,
                currency="USD",
                image_url="https://example.com/2.jpg",
                product_url="https://example.com/2",
                color_tags=None,
            ),
            Product(
                id="p_top_3",
                title="Premium Tee",
                brand="C",
                category="top",
                price=80,
                currency="USD",
                image_url="https://example.com/3.jpg",
                product_url="https://example.com/3",
                color_tags=None,
            ),
        ]
    )

    capture = Capture(user_id=user.id, image_path=str(sample_image_path), status="queued")
    db_session.add(capture)
    db_session.commit()

    monkeypatch.setattr("app.services.pipeline_executor.CapturePipeline", _MockPipeline)
    monkeypatch.setattr("app.services.pipeline_executor.get_catalog", lambda: _MockCatalog())

    class _FakeTaste:
        def update_embedding(self, prev, cur):
            return cur

        def radar_scores(self, emb):
            return {
                "minimal_maximal": 55.0,
                "structured_relaxed": 48.0,
                "neutral_color_forward": 52.0,
                "classic_experimental": 49.0,
                "casual_formal": 51.0,
            }

        def delta(self, old, new):
            return {k: new[k] - (old or {}).get(k, 0.0) for k in new}

    monkeypatch.setattr("app.services.pipeline_executor.TasteProfileEngine", lambda: _FakeTaste())

    process_capture(db_session, capture.id, notifier=_FailingNotifier())

    updated = db_session.query(Capture).filter(Capture.id == capture.id).first()
    assert updated is not None
    assert updated.status == "done"
    assert len(updated.garments) == 1
    assert len(updated.matches) >= 1

    process_capture(db_session, capture.id, notifier=_FailingNotifier())

    refreshed = db_session.query(Capture).filter(Capture.id == capture.id).first()
    assert refreshed is not None
    assert len(refreshed.garments) == 1
    assert len(refreshed.matches) >= 1
