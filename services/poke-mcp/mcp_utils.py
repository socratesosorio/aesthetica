from __future__ import annotations

import time
from datetime import datetime
from typing import Any


def now_ms() -> int:
    return int(time.perf_counter() * 1000)


def elapsed_ms(start_ms: int) -> int:
    return max(0, now_ms() - start_ms)


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def clip_text(value: Any, max_chars: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def ok_response(
    intent: str,
    data: dict[str, Any],
    timing_ms: dict[str, int] | None = None,
    next_actions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok",
        "intent": intent,
        "data": data,
    }
    if timing_ms:
        payload["timing_ms"] = timing_ms
    if next_actions:
        payload["next_actions"] = next_actions
    return payload


def error_response(
    intent: str,
    error_code: str,
    message: str,
    timing_ms: dict[str, int] | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
        "intent": intent,
        "error_code": error_code,
        "message": clip_text(message, 220),
    }
    if timing_ms:
        payload["timing_ms"] = timing_ms
    if data:
        payload["data"] = data
    return payload
