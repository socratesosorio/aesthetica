from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class PokeNotifier:
    def send(self, message: str) -> None:
        if not settings.poke_api_key:
            logger.warning("poke_key_missing_skip_send")
            return

        headers = {"Authorization": f"Bearer {settings.poke_api_key}"}
        payload = {"message": message[:800]}
        try:
            resp = httpx.post(settings.poke_webhook_url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("poke_sent")
        except Exception:
            logger.exception("poke_send_failed")
