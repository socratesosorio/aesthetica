from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class MLConfig:
    openclip_model_name: str = os.getenv("OPENCLIP_MODEL_NAME", "ViT-B-32")
    openclip_pretrained: str = os.getenv("OPENCLIP_PRETRAINED", "laion2b_s34b_b79k")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "512"))
    model_device: str = os.getenv("MODEL_DEVICE", "cpu")
    faiss_dir: str = os.getenv("FAISS_DIR", "/app/data/faiss")
    product_csv_path: str = os.getenv("PRODUCT_CSV_PATH", "/app/data/products.csv")
    radar_scale: float = float(os.getenv("RADAR_SCALE", "50"))
    radar_bias: float = float(os.getenv("RADAR_BIAS", "50"))
    radar_alpha: float = float(os.getenv("RADAR_ALPHA", "0.85"))


CONFIG = MLConfig()
