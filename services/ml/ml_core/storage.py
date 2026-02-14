from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .utils import ensure_dir


class StorageBackend:
    def put_bytes(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def resolve(self, key: str) -> str:
        raise NotImplementedError


@dataclass(slots=True)
class LocalStorage(StorageBackend):
    root: str

    def __post_init__(self) -> None:
        ensure_dir(self.root)

    def put_bytes(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        path = Path(self.root) / key
        ensure_dir(path.parent)
        path.write_bytes(data)
        return str(path)

    def read_bytes(self, key: str) -> bytes:
        p = Path(key)
        if p.is_absolute():
            return p.read_bytes()

        root = Path(self.root)
        # `put_bytes` can persist keys that already include the configured root
        # (for example "data/uploads/..."). Avoid prefixing root twice.
        if root.parts and p.parts[: len(root.parts)] == root.parts:
            return p.read_bytes()

        return Path(self.root, key).read_bytes()

    def resolve(self, key: str) -> str:
        return str(Path(self.root, key))


@dataclass(slots=True)
class S3Storage(StorageBackend):
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str

    def __post_init__(self) -> None:
        import boto3

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            self._client.create_bucket(Bucket=self.bucket)

    def put_bytes(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def read_bytes(self, key: str) -> bytes:
        bucket = self.bucket
        object_key = key
        if key.startswith("s3://"):
            parsed = urlparse(key)
            if parsed.netloc and parsed.path:
                bucket = parsed.netloc
                object_key = parsed.path.lstrip("/")
        body = self._client.get_object(Bucket=bucket, Key=object_key)["Body"].read()
        return bytes(body)

    def resolve(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"


def get_storage() -> StorageBackend:
    backend = os.getenv("STORAGE_BACKEND", "local")
    if backend == "s3":
        return S3Storage(
            endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://minio:9000"),
            access_key=os.getenv("S3_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("S3_SECRET_KEY", "minioadmin"),
            bucket=os.getenv("S3_BUCKET", "aesthetica"),
        )
    return LocalStorage(root=os.getenv("LOCAL_STORAGE_ROOT", "/app/data/uploads"))
