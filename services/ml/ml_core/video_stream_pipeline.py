"""Real-time video stream pipeline for Meta Ray-Ban DAT integration.

Receives a continuous stream of JPEG frames from the glasses (via the mobile
companion app), performs keyframe selection based on perceptual difference, and
runs the full capture pipeline only on frames that represent meaningful scene
changes.  This avoids redundant ML work while still capturing every interesting
outfit the wearer walks past.

Typical flow
────────────
 glasses ─DAT→ mobile ─WS→ backend
                              │
                    VideoStreamPipeline
                       ├─ frame buffer
                       ├─ keyframe selector (SSIM / pixel-diff)
                       └─ CapturePipeline.run()  ← only on keyframes
                              │
                    StreamResult  ─WS→  mobile (live overlay)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from io import BytesIO
from typing import Callable

import cv2
import numpy as np
from PIL import Image

from .pipeline import CapturePipeline, CaptureInference

logger = logging.getLogger(__name__)


# ── dataclasses ──────────────────────────────────────────────────────────────


@dataclass(slots=True)
class FrameMeta:
    """Metadata attached to every ingested frame."""

    seq: int
    timestamp: float
    jpeg_size: int
    is_keyframe: bool = False


@dataclass(slots=True)
class StreamResult:
    """Payload returned to the client for each processed keyframe."""

    seq: int
    timestamp: float
    inference: CaptureInference
    processing_ms: float
    garment_summaries: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class StreamStats:
    """Rolling statistics for the stream session."""

    frames_received: int = 0
    keyframes_detected: int = 0
    frames_skipped: int = 0
    avg_processing_ms: float = 0.0
    last_keyframe_seq: int = -1
    session_start: float = field(default_factory=time.time)

    @property
    def uptime_s(self) -> float:
        return time.time() - self.session_start

    @property
    def effective_fps(self) -> float:
        if self.uptime_s <= 0:
            return 0.0
        return self.frames_received / self.uptime_s

    def to_dict(self) -> dict:
        return {
            "frames_received": self.frames_received,
            "keyframes_detected": self.keyframes_detected,
            "frames_skipped": self.frames_skipped,
            "avg_processing_ms": round(self.avg_processing_ms, 1),
            "effective_fps": round(self.effective_fps, 1),
            "uptime_s": round(self.uptime_s, 1),
        }


# ── keyframe selector ────────────────────────────────────────────────────────


class KeyframeSelector:
    """Decides whether a frame is *different enough* from the last keyframe to
    warrant running the full ML pipeline.

    Uses a combination of:
      - Structural similarity (SSIM) computed on down-scaled grayscale thumbnails.
      - Minimum time gap between keyframes (to avoid bursts).
      - Maximum time gap (force a keyframe after N seconds of inactivity).
    """

    def __init__(
        self,
        *,
        ssim_threshold: float = 0.85,
        pixel_diff_threshold: float = 0.06,
        min_interval_s: float = 1.0,
        max_interval_s: float = 10.0,
        thumbnail_size: tuple[int, int] = (160, 120),
    ) -> None:
        self.ssim_threshold = ssim_threshold
        self.pixel_diff_threshold = pixel_diff_threshold
        self.min_interval_s = min_interval_s
        self.max_interval_s = max_interval_s
        self.thumbnail_size = thumbnail_size

        self._last_gray: np.ndarray | None = None
        self._last_keyframe_time: float = 0.0

    def _to_gray_thumb(self, frame_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, self.thumbnail_size, interpolation=cv2.INTER_AREA)

    @staticmethod
    def _compute_ssim(a: np.ndarray, b: np.ndarray) -> float:
        """Simplified mean SSIM between two single-channel images."""
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        a = a.astype(np.float64)
        b = b.astype(np.float64)

        mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
        mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)

        mu_a_sq = mu_a ** 2
        mu_b_sq = mu_b ** 2
        mu_ab = mu_a * mu_b

        sigma_a_sq = cv2.GaussianBlur(a ** 2, (11, 11), 1.5) - mu_a_sq
        sigma_b_sq = cv2.GaussianBlur(b ** 2, (11, 11), 1.5) - mu_b_sq
        sigma_ab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_ab

        num = (2 * mu_ab + C1) * (2 * sigma_ab + C2)
        den = (mu_a_sq + mu_b_sq + C1) * (sigma_a_sq + sigma_b_sq + C2)

        ssim_map = num / den
        return float(ssim_map.mean())

    @staticmethod
    def _mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))) / 255.0)

    def check(self, frame_bgr: np.ndarray, now: float | None = None) -> bool:
        """Return True if *frame_bgr* should be treated as a keyframe."""
        now = now or time.time()
        gray = self._to_gray_thumb(frame_bgr)

        # First frame is always a keyframe.
        if self._last_gray is None:
            self._last_gray = gray
            self._last_keyframe_time = now
            return True

        elapsed = now - self._last_keyframe_time

        # Enforce minimum gap.
        if elapsed < self.min_interval_s:
            return False

        # Force keyframe after max gap.
        if elapsed >= self.max_interval_s:
            self._last_gray = gray
            self._last_keyframe_time = now
            return True

        # Check pixel-level difference (fast).
        diff = self._mean_abs_diff(gray, self._last_gray)
        if diff < self.pixel_diff_threshold:
            return False

        # Check structural similarity (more robust).
        ssim = self._compute_ssim(gray, self._last_gray)
        if ssim > self.ssim_threshold:
            return False

        self._last_gray = gray
        self._last_keyframe_time = now
        return True

    def reset(self) -> None:
        self._last_gray = None
        self._last_keyframe_time = 0.0


# ── stream pipeline ──────────────────────────────────────────────────────────


class VideoStreamPipeline:
    """Wraps :class:`CapturePipeline` for continuous video-frame ingestion.

    Parameters
    ----------
    capture_pipeline:
        The existing single-image ML pipeline.
    on_result:
        Optional callback invoked with each :class:`StreamResult`.
    keyframe_selector:
        Custom :class:`KeyframeSelector`, or *None* for defaults.
    max_buffer:
        Maximum number of unprocessed keyframes to buffer.  Oldest are dropped
        if the pipeline can't keep up.
    """

    def __init__(
        self,
        capture_pipeline: CapturePipeline,
        *,
        on_result: Callable[[StreamResult], None] | None = None,
        keyframe_selector: KeyframeSelector | None = None,
        max_buffer: int = 8,
    ) -> None:
        self.pipeline = capture_pipeline
        self.on_result = on_result
        self.selector = keyframe_selector or KeyframeSelector()
        self.stats = StreamStats()

        self._buffer: deque[tuple[int, float, Image.Image]] = deque(maxlen=max_buffer)
        self._seq = 0
        self._processing_times: deque[float] = deque(maxlen=50)
        self._stopped = False

    # ── public API ───────────────────────────────────────────────────────

    def ingest_jpeg(self, jpeg_bytes: bytes) -> FrameMeta:
        """Ingest a single JPEG frame from the DAT stream.

        Returns frame metadata indicating whether it was selected as a
        keyframe.  If it *is* a keyframe, it's placed on the internal
        buffer for :meth:`process_next` to pick up.
        """
        self._seq += 1
        seq = self._seq
        now = time.time()
        self.stats.frames_received += 1

        meta = FrameMeta(seq=seq, timestamp=now, jpeg_size=len(jpeg_bytes))

        # Decode JPEG → OpenCV BGR for keyframe check.
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame_bgr is None:
            logger.warning("stream_frame_decode_failed seq=%d", seq)
            self.stats.frames_skipped += 1
            return meta

        if self.selector.check(frame_bgr, now):
            meta.is_keyframe = True
            self.stats.keyframes_detected += 1
            self.stats.last_keyframe_seq = seq

            # Convert to PIL for the capture pipeline.
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            self._buffer.append((seq, now, pil))
        else:
            self.stats.frames_skipped += 1

        return meta

    def process_next(self) -> StreamResult | None:
        """Process the oldest buffered keyframe through the ML pipeline.

        Returns *None* if the buffer is empty.
        """
        if not self._buffer:
            return None

        seq, ts, pil_image = self._buffer.popleft()

        t0 = time.time()
        try:
            inference = self.pipeline.run(pil_image)
        except Exception:
            logger.exception("stream_pipeline_run_failed seq=%d", seq)
            return None
        elapsed_ms = (time.time() - t0) * 1000.0

        self._processing_times.append(elapsed_ms)
        self.stats.avg_processing_ms = sum(self._processing_times) / len(self._processing_times)

        garment_summaries = [
            {
                "garment_type": g.garment_type,
                "attributes": g.attributes,
            }
            for g in inference.garments
        ]

        result = StreamResult(
            seq=seq,
            timestamp=ts,
            inference=inference,
            processing_ms=elapsed_ms,
            garment_summaries=garment_summaries,
        )

        if self.on_result is not None:
            try:
                self.on_result(result)
            except Exception:
                logger.exception("stream_on_result_callback_failed")

        return result

    def drain(self) -> list[StreamResult]:
        """Process all buffered keyframes and return results."""
        results: list[StreamResult] = []
        while self._buffer:
            r = self.process_next()
            if r is not None:
                results.append(r)
        return results

    @property
    def buffer_depth(self) -> int:
        return len(self._buffer)

    @property
    def has_pending(self) -> bool:
        return len(self._buffer) > 0

    def reset(self) -> None:
        """Reset stream state for a new session."""
        self._buffer.clear()
        self._seq = 0
        self._processing_times.clear()
        self.selector.reset()
        self.stats = StreamStats()
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True
