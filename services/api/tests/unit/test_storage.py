from __future__ import annotations

from pathlib import Path

from ml_core.storage import LocalStorage


def test_local_storage_reads_paths_with_relative_root_prefix(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)

    storage = LocalStorage(root="data/uploads")
    key = "captures/test.jpg"
    expected_path = Path(storage.put_bytes(key, b"abc123", content_type="image/jpeg"))

    assert expected_path == Path("data/uploads/captures/test.jpg")
    assert storage.read_bytes(str(expected_path)) == b"abc123"
    assert storage.read_bytes(key) == b"abc123"
