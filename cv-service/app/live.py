"""Single-process live worker. Reject excess work; never queue camera frames."""
import io
import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock, RLock
from uuid import UUID

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, HTTPException, Request, Query
from starlette.concurrency import run_in_threadpool
from app.detection.detector import get_detector
from app.tracking.config import TrackingConfig
from app.tracking.tracker import PersonTracker
from app.crowd.config import from_environment
from app.crowd.analysis import image_occupancy, crowd_concentration
from app.crowd.schemas import count_trend

router = APIRouter(prefix='/live/sessions')
MAX_BYTES = int(os.getenv('LIVE_MAX_FRAME_BYTES', '524288'))
MAX_PIXELS = int(os.getenv('LIVE_MAX_FRAME_PIXELS', '921600'))
TTL = float(os.getenv('LIVE_WORKER_IDLE_SECONDS', '120'))
CAPACITY = int(os.getenv('LIVE_MAX_SESSIONS', '8'))


@dataclass
class Processor:
    sequence: int = 0
    capture: float = -1
    touched: float = field(default_factory=time.monotonic)
    tracker: object = None
    dimensions: tuple | None = None
    counts: deque = field(default_factory=lambda: deque(maxlen=10))
    lock: Lock = field(default_factory=Lock)

    def process(self, data, sequence, capture):
        if sequence <= self.sequence or capture <= self.capture:
            raise HTTPException(409, 'Frame sequence and capture timestamp must advance')
        frame = decode(data)
        height, width = frame.shape[:2]
        if self.dimensions and self.dimensions != (width, height):
            raise HTTPException(422, 'Frame dimensions must remain fixed within a session')
        started = time.perf_counter()
        config = TrackingConfig.from_environment()
        detector = get_detector(os.getenv('YOLO_MODEL', 'yolo11n.pt'),
            min(float(os.getenv('YOLO_CONFIDENCE_THRESHOLD', '.35')), config.track_low_thresh),
            int(os.getenv('YOLO_IMAGE_SIZE', '640')))
        if self.tracker is None:
            self.tracker = PersonTracker(config, width, height)
            self.dimensions = (width, height)
        tracks = self.tracker.update(detector.detect(frame))
        count = len(tracks)
        delta = count-self.counts[-1] if self.counts else 0
        self.counts.append(count)
        self.sequence, self.capture = sequence, capture
        self.touched = time.monotonic()
        crowd = from_environment()
        return dict(sequence=sequence, capture_timestamp=capture, width=width, height=height,
            tracks=[t.model_dump() for t in tracks], observed_crowd_count=count,
            image_occupancy_ratio=image_occupancy(tracks, width, height),
            crowd_concentration=crowd_concentration(tracks, width, height), crowd_level=crowd.level(count),
            crowd_count_delta=delta, crowd_trend=count_trend(list(self.counts), crowd),
            processing_duration_seconds=time.perf_counter()-started)


def decode(data):
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, 'Frame must be non-empty and within byte limit')
    try:
        with Image.open(io.BytesIO(data)) as header:
            if header.format not in ('JPEG', 'WEBP') or min(header.size) < 16 or max(header.size) > 1920 or header.width*header.height > MAX_PIXELS:
                raise ValueError('Invalid dimensions or format')
            header.verify()
        frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError('Decode failed')
        return frame
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(422, 'Invalid JPEG/WebP frame or dimensions') from None


states: dict[UUID, Processor] = {}
registry = RLock()
inference = Lock()


def reap():
    with registry:
        for key, state in list(states.items()):
            if time.monotonic()-state.touched > TTL and state.lock.acquire(False):
                del states[key]
                state.lock.release()


@router.post('/{session_id}/start')
def start(session_id: UUID):
    reap()
    with registry:
        if session_id in states:
            return {'status': 'RUNNING'}
        if len(states) >= CAPACITY:
            raise HTTPException(503, 'Live worker capacity reached')
        states[session_id] = Processor()
    return {'status': 'RUNNING'}


@router.post('/{session_id}/stop')
def stop(session_id: UUID):
    with registry:
        state = states.get(session_id)
    if state:
        with state.lock:
            with registry:
                states.pop(session_id, None)
    return {'status': 'STOPPED'}


@router.post('/{session_id}/frame')
async def frame(session_id: UUID, request: Request, sequence: int = Query(ge=1),
                capture_timestamp: float = Query(ge=0, allow_inf_nan=False)):
    if request.headers.get('content-type', '').split(';')[0] not in ('image/jpeg', 'image/webp'):
        raise HTTPException(415, 'Use binary JPEG or WebP')
    with registry:
        state = states.get(session_id)
        if not state:
            raise HTTPException(410, 'Live worker state lost or expired; start a new session')
        if not state.lock.acquire(False):
            raise HTTPException(429, 'Frame dropped: session busy')
    acquired = inference.acquire(False)
    try:
        if not acquired:
            raise HTTPException(429, 'Frame dropped: inference busy')
        data = bytearray()
        try:
            async with asyncio.timeout(10):
                async for chunk in request.stream():
                    if len(data)+len(chunk) > MAX_BYTES:
                        raise HTTPException(413, 'Frame exceeds byte limit')
                    data.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, 'Frame upload timed out') from None
        return await run_in_threadpool(state.process, bytes(data), sequence, capture_timestamp)
    except HTTPException:
        raise
    except Exception:
        with registry:
            states.pop(session_id, None)
        raise HTTPException(503, 'Live processing failed; session state released') from None
    finally:
        if acquired:
            inference.release()
        state.lock.release()
