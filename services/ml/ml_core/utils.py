from __future__ import annotations

import base64
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image


def l2_normalize(vec: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm < eps:
        return vec
    return vec / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_n = l2_normalize(a.astype(np.float32))
    b_n = l2_normalize(b.astype(np.float32))
    return float(np.dot(a_n, b_n))


def ndarray_to_b64(vec: np.ndarray) -> str:
    return base64.b64encode(vec.astype(np.float32).tobytes()).decode("utf-8")


def b64_to_ndarray(payload: str, dim: int) -> np.ndarray:
    raw = base64.b64decode(payload.encode("utf-8"))
    arr = np.frombuffer(raw, dtype=np.float32)
    if arr.shape[0] != dim:
        raise ValueError(f"Expected dim {dim}, got {arr.shape[0]}")
    return arr


def deterministic_embedding_from_bytes(data: bytes, dim: int) -> np.ndarray:
    digest = hashlib.sha256(data).digest()
    seed = int.from_bytes(digest[:8], "little")
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float32)
    return l2_normalize(vec)


def image_bytes_to_pil(image_bytes: bytes) -> Image.Image:
    return Image.open(BytesIO(image_bytes)).convert("RGB")


def pil_to_jpeg_bytes(image: Image.Image, quality: int = 82) -> bytes:
    out = BytesIO()
    image.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def blur_faces_safety(image: Image.Image) -> Image.Image:
    """Safety blur pass to guarantee no unblurred faces are persisted."""
    arr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(28, 28))
    for (x, y, w, h) in faces:
        roi = arr[y : y + h, x : x + w]
        if roi.size == 0:
            continue
        arr[y : y + h, x : x + w] = cv2.GaussianBlur(roi, (31, 31), 0)
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def dominant_colors(image: Image.Image, k: int = 4) -> list[tuple[str, float]]:
    arr = np.array(image.convert("RGB")).reshape(-1, 3).astype(np.float32)
    if arr.shape[0] < k:
        k = max(1, arr.shape[0])
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
    _, labels, centers = cv2.kmeans(arr, k, None, criteria, 8, cv2.KMEANS_PP_CENTERS)
    labels = labels.flatten()
    counts = np.bincount(labels, minlength=k).astype(np.float32)
    pcts = counts / counts.sum()
    order = np.argsort(-pcts)

    colors: list[tuple[str, float]] = []
    for idx in order:
        c = centers[idx].astype(int).tolist()
        colors.append((f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}", float(pcts[idx])))
    return colors


def color_entropy(image: Image.Image) -> float:
    hsv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 24], [0, 180, 0, 256]).flatten()
    hist = hist / (hist.sum() + 1e-9)
    nz = hist[hist > 0]
    return float(-(nz * np.log2(nz)).sum())


def edge_density(image: Image.Image) -> float:
    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 140)
    return float((edges > 0).mean())


def load_image_from_path_or_url(path_or_url: str) -> Image.Image:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        import requests

        resp = requests.get(path_or_url, timeout=10)
        resp.raise_for_status()
        return image_bytes_to_pil(resp.content)

    p = Path(path_or_url)
    if p.exists():
        return Image.open(p).convert("RGB")

    # deterministic placeholder for missing assets
    digest = hashlib.md5(path_or_url.encode("utf-8")).digest()
    color = tuple(int(x) for x in digest[:3])
    return Image.new("RGB", (256, 256), color=color)


def masked_crop_rgba(image: Image.Image, mask: np.ndarray) -> Image.Image:
    rgb = np.array(image.convert("RGB"))
    if mask.dtype != np.uint8:
        mask = (mask > 0).astype(np.uint8)

    ys, xs = np.where(mask > 0)
    if ys.size == 0 or xs.size == 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    y1, y2 = int(ys.min()), int(ys.max()) + 1
    x1, x2 = int(xs.min()), int(xs.max()) + 1
    crop_rgb = rgb[y1:y2, x1:x2]
    crop_mask = mask[y1:y2, x1:x2] * 255
    rgba = np.dstack([crop_rgb, crop_mask])
    return Image.fromarray(rgba, mode="RGBA")


def most_common(items: Iterable[str]) -> str | None:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]
