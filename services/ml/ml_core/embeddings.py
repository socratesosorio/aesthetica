from __future__ import annotations

import threading
from functools import lru_cache
from typing import Iterable

import numpy as np
from PIL import Image

from .config import CONFIG
from .utils import deterministic_embedding_from_bytes, l2_normalize


class OpenClipEmbedder:
    """OpenCLIP wrapper with deterministic fallback if model weights are unavailable."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._fallback = False
        self._model = None
        self._preprocess = None
        self._tokenizer = None

    def _lazy_load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            try:
                import open_clip
                import torch

                model, _, preprocess = open_clip.create_model_and_transforms(
                    CONFIG.openclip_model_name,
                    pretrained=CONFIG.openclip_pretrained,
                    device=CONFIG.model_device,
                )
                tokenizer = open_clip.get_tokenizer(CONFIG.openclip_model_name)
                model.eval()
                self._model = model
                self._preprocess = preprocess
                self._tokenizer = tokenizer
                self._fallback = False
            except Exception:
                self._fallback = True
            self._loaded = True

    def image_embedding(self, image: Image.Image) -> np.ndarray:
        self._lazy_load()
        if self._fallback:
            data = image.tobytes()
            return deterministic_embedding_from_bytes(data, CONFIG.embedding_dim)

        import torch

        assert self._preprocess is not None
        assert self._model is not None

        tensor = self._preprocess(image).unsqueeze(0)
        tensor = tensor.to(CONFIG.model_device)
        with torch.no_grad():
            feats = self._model.encode_image(tensor).cpu().numpy()[0].astype(np.float32)
        return l2_normalize(feats)

    def text_embedding(self, text: str) -> np.ndarray:
        self._lazy_load()
        if self._fallback:
            return deterministic_embedding_from_bytes(text.encode("utf-8"), CONFIG.embedding_dim)

        import torch

        assert self._tokenizer is not None
        assert self._model is not None

        tokens = self._tokenizer([text]).to(CONFIG.model_device)
        with torch.no_grad():
            feats = self._model.encode_text(tokens).cpu().numpy()[0].astype(np.float32)
        return l2_normalize(feats)

    def batch_image_embeddings(self, images: Iterable[Image.Image]) -> list[np.ndarray]:
        return [self.image_embedding(image) for image in images]


@lru_cache(maxsize=1)
def get_embedder() -> OpenClipEmbedder:
    return OpenClipEmbedder()
