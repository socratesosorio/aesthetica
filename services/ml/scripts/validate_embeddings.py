#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
from PIL import Image

from ml_core.config import CONFIG
from ml_core.embeddings import get_embedder
from ml_core.utils import cosine_similarity


def main() -> None:
    embedder = get_embedder()

    img_a = Image.new("RGB", (224, 224), color=(120, 120, 120))
    img_b = Image.new("RGB", (224, 224), color=(200, 50, 50))

    va = embedder.image_embedding(img_a)
    vb = embedder.image_embedding(img_b)

    assert va.shape[0] == CONFIG.embedding_dim, f"Expected {CONFIG.embedding_dim}, got {va.shape[0]}"
    assert vb.shape[0] == CONFIG.embedding_dim, f"Expected {CONFIG.embedding_dim}, got {vb.shape[0]}"

    sim_same = cosine_similarity(va, va)
    sim_diff = cosine_similarity(va, vb)

    print(f"dim={va.shape[0]} sim_same={sim_same:.4f} sim_diff={sim_diff:.4f}")
    assert sim_same > sim_diff


if __name__ == "__main__":
    main()
