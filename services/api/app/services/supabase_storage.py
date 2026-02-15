from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import requests

from app.core.config import settings


@dataclass(slots=True)
class SupabaseUploadResult:
    bucket: str
    object_path: str
    public_url: str | None


def upload_catalog_input_image(
    request_id: str,
    image_bytes: bytes,
    content_type: str | None,
    filename: str | None,
) -> SupabaseUploadResult | None:
    """
    Best-effort upload of catalog input image to Supabase Storage.
    Returns None when storage config is not enabled or incomplete.
    Raises RuntimeError on upload failure.
    """
    if not settings.supabase_store_catalog_input:
        return None
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    ext = _infer_ext(content_type=content_type, filename=filename)
    object_path = f"catalog-inputs/{request_id}{ext}"
    bucket = settings.supabase_storage_bucket
    encoded_path = quote(object_path, safe="/._-")
    base = settings.supabase_url.rstrip("/")
    upload_url = f"{base}/storage/v1/object/{bucket}/{encoded_path}"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": (content_type or "application/octet-stream"),
        "x-upsert": "true",
    }
    resp = requests.post(upload_url, headers=headers, data=image_bytes, timeout=20)
    if resp.status_code >= 400:
        raise RuntimeError(f"Supabase upload failed: {resp.status_code} {resp.text[:300]}")

    public_url = f"{base}/storage/v1/object/public/{bucket}/{encoded_path}"
    return SupabaseUploadResult(bucket=bucket, object_path=object_path, public_url=public_url)


def _infer_ext(content_type: str | None, filename: str | None) -> str:
    if content_type:
        c = content_type.lower().strip()
        if c in {"image/jpeg", "image/jpg"}:
            return ".jpg"
        if c == "image/png":
            return ".png"
        if c == "image/webp":
            return ".webp"
    if filename and "." in filename:
        tail = filename.rsplit(".", 1)[-1].lower().strip()
        if tail in {"jpg", "jpeg", "png", "webp"}:
            return ".jpg" if tail == "jpeg" else f".{tail}"
    return ".jpg"
