"""WebSocket endpoint for real-time video streaming from Meta Ray-Ban glasses.

Protocol
────────
Client (mobile app) connects to ``ws://.../v1/stream?token=<jwt-or-dev>``.

**Client → Server (binary):**
    Raw JPEG frame bytes from the DAT video stream.

**Client → Server (text/JSON):**
    Control messages:
      - ``{"type": "configure", "ssim_threshold": 0.85, "min_interval_s": 1.0, ...}``
      - ``{"type": "ping"}``
      - ``{"type": "stop"}``

**Server → Client (text/JSON):**
    - ``{"type": "ack",       "seq": N, "is_keyframe": bool}``
    - ``{"type": "result",    "seq": N, "garments": [...], "processing_ms": float, "stats": {...}}``
    - ``{"type": "stats",     ...}``
    - ``{"type": "pong"}``
    - ``{"type": "error",     "detail": "..."}``
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models import User

from ml_core.pipeline import CapturePipeline
from ml_core.retrieval import get_catalog
from ml_core.video_stream_pipeline import (
    KeyframeSelector,
    VideoStreamPipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────


def _authenticate_ws(token: str) -> str | None:
    """Return user-id if the token is valid, else None."""
    if token == "dev":
        # Dev shortcut — grab first user.
        for db in get_db_session():
            user = db.query(User).first()
            if user is not None:
                return user.id
        return None

    try:
        return decode_access_token(token)
    except Exception:
        return None


async def _send_json(ws: WebSocket, payload: dict) -> None:
    if ws.client_state == WebSocketState.CONNECTED:
        await ws.send_text(json.dumps(payload))


def _build_result_payload(result) -> dict:
    """Serialize a StreamResult into a JSON-safe dict."""
    garments = []
    for g in result.garment_summaries:
        garments.append({
            "garment_type": g.get("garment_type", "unknown"),
            "attributes": g.get("attributes", {}),
        })

    return {
        "type": "result",
        "seq": result.seq,
        "timestamp": result.timestamp,
        "garments": garments,
        "processing_ms": round(result.processing_ms, 1),
    }


# ── websocket endpoint ──────────────────────────────────────────────────────


@router.websocket("/stream")
async def video_stream(
    ws: WebSocket,
    token: str = Query("dev"),
) -> None:
    """Real-time video stream endpoint.

    Frames are received as binary WebSocket messages (JPEG bytes) and fed
    into :class:`VideoStreamPipeline`.  Only keyframes are processed; all
    frames receive a lightweight ``ack`` so the client can track delivery.
    """
    user_id = _authenticate_ws(token)
    if user_id is None:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    logger.info("stream_ws_connected user=%s", user_id)

    # Build pipeline for this session.
    catalog = get_catalog()
    capture_pipeline = CapturePipeline(catalog=catalog)
    selector = KeyframeSelector()
    stream = VideoStreamPipeline(capture_pipeline, keyframe_selector=selector)

    # Background task: drain the processing buffer and send results back.
    result_queue: asyncio.Queue[dict] = asyncio.Queue()
    processing = True

    async def _process_loop() -> None:
        """Run the ML pipeline on buffered keyframes in a thread executor."""
        loop = asyncio.get_running_loop()
        while processing:
            if stream.has_pending:
                result = await loop.run_in_executor(None, stream.process_next)
                if result is not None:
                    payload = _build_result_payload(result)
                    payload["stats"] = stream.stats.to_dict()
                    await result_queue.put(payload)
            else:
                await asyncio.sleep(0.05)

    async def _send_results() -> None:
        """Forward processed results from queue to WebSocket."""
        while processing:
            try:
                payload = await asyncio.wait_for(result_queue.get(), timeout=0.5)
                await _send_json(ws, payload)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    process_task = asyncio.create_task(_process_loop())
    send_task = asyncio.create_task(_send_results())

    # Periodic stats beacon.
    last_stats_time = time.time()
    STATS_INTERVAL = 5.0

    try:
        while True:
            message = await ws.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # Binary message → JPEG frame.
            if "bytes" in message and message["bytes"]:
                jpeg_data: bytes = message["bytes"]
                loop = asyncio.get_running_loop()
                meta = await loop.run_in_executor(
                    None, stream.ingest_jpeg, jpeg_data
                )

                await _send_json(ws, {
                    "type": "ack",
                    "seq": meta.seq,
                    "is_keyframe": meta.is_keyframe,
                    "jpeg_size": meta.jpeg_size,
                    "buffer_depth": stream.buffer_depth,
                })

                # Periodic stats.
                now = time.time()
                if now - last_stats_time >= STATS_INTERVAL:
                    last_stats_time = now
                    await _send_json(ws, {
                        "type": "stats",
                        **stream.stats.to_dict(),
                    })

            # Text message → control command.
            elif "text" in message and message["text"]:
                try:
                    cmd = json.loads(message["text"])
                except json.JSONDecodeError:
                    await _send_json(ws, {"type": "error", "detail": "Invalid JSON"})
                    continue

                msg_type = cmd.get("type", "")

                if msg_type == "ping":
                    await _send_json(ws, {"type": "pong"})

                elif msg_type == "configure":
                    # Allow live-tuning of keyframe parameters.
                    if "ssim_threshold" in cmd:
                        selector.ssim_threshold = float(cmd["ssim_threshold"])
                    if "pixel_diff_threshold" in cmd:
                        selector.pixel_diff_threshold = float(cmd["pixel_diff_threshold"])
                    if "min_interval_s" in cmd:
                        selector.min_interval_s = float(cmd["min_interval_s"])
                    if "max_interval_s" in cmd:
                        selector.max_interval_s = float(cmd["max_interval_s"])
                    await _send_json(ws, {"type": "configured", "params": {
                        "ssim_threshold": selector.ssim_threshold,
                        "pixel_diff_threshold": selector.pixel_diff_threshold,
                        "min_interval_s": selector.min_interval_s,
                        "max_interval_s": selector.max_interval_s,
                    }})

                elif msg_type == "stats":
                    await _send_json(ws, {
                        "type": "stats",
                        **stream.stats.to_dict(),
                    })

                elif msg_type == "stop":
                    break

                else:
                    await _send_json(ws, {"type": "error", "detail": f"Unknown command: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("stream_ws_disconnected user=%s", user_id)
    except Exception:
        logger.exception("stream_ws_error user=%s", user_id)
    finally:
        processing = False
        stream.stop()
        process_task.cancel()
        send_task.cancel()

        try:
            await process_task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await send_task
        except (asyncio.CancelledError, Exception):
            pass

        final_stats = stream.stats.to_dict()
        logger.info("stream_session_ended user=%s stats=%s", user_id, final_stats)

        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close()
