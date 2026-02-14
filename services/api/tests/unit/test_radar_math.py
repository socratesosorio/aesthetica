from __future__ import annotations

import hashlib

import numpy as np

from ml_core.taste import TasteProfileEngine


class _FakeEmbedder:
    def text_embedding(self, text: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(512).astype(np.float32)
        return vec / np.linalg.norm(vec)


def test_radar_engine_update_and_bounds(monkeypatch):
    monkeypatch.setattr("ml_core.taste.get_embedder", lambda: _FakeEmbedder())

    engine = TasteProfileEngine(alpha=0.85, scale=50.0, bias=50.0)
    prev = np.ones(512, dtype=np.float32)
    prev = prev / np.linalg.norm(prev)
    cap = np.zeros(512, dtype=np.float32)
    cap[0] = 1.0

    updated = engine.update_embedding(prev, cap)
    assert updated.shape == (512,)
    assert np.isclose(np.linalg.norm(updated), 1.0, atol=1e-5)

    radar = engine.radar_scores(updated)
    assert len(radar) == 5
    for value in radar.values():
        assert 0.0 <= value <= 100.0

    delta = engine.delta({k: 50.0 for k in radar}, radar)
    assert set(delta.keys()) == set(radar.keys())
