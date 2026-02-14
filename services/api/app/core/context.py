from __future__ import annotations

from contextvars import ContextVar

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
capture_id_ctx: ContextVar[str | None] = ContextVar("capture_id", default=None)
