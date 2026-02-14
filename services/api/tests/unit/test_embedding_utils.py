from __future__ import annotations

import numpy as np

from ml_core.utils import b64_to_ndarray, cosine_similarity, ndarray_to_b64


def test_b64_roundtrip_and_cosine():
    vec = np.random.default_rng(7).standard_normal(512).astype(np.float32)
    payload = ndarray_to_b64(vec)
    decoded = b64_to_ndarray(payload, 512)

    assert decoded.shape == (512,)
    assert np.allclose(vec, decoded)
    assert cosine_similarity(vec, vec) > 0.999
