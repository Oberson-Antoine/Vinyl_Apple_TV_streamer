from dataclasses import dataclass, field
from datetime import datetime

from app.audio.ring_buffer import RingBuffer
from app.owntone.client import OwnToneClient


@dataclass
class NowPlaying:
    title: str
    artist: str
    recognized_at: datetime
    artwork_url: str | None = None


@dataclass
class AppState:
    """Shared in-memory state written by the background tasks and read by the REST
    API. Only `now_playing` is mutated from more than one place with any real
    concurrency risk (recognizer writes, API reads) — plain attribute reads/writes are
    fine here since everything runs on a single asyncio event loop thread; no lock
    needed unless a field starts being mutated from a thread instead of a task."""

    ring_buffer: RingBuffer
    owntone_client: OwnToneClient

    capture_alive: bool = False
    last_capture_chunk_at: datetime | None = None
    capture_dropped_chunks: int = 0

    fifo_connected: bool = False

    now_playing: NowPlaying | None = None
    consecutive_no_match: int = 0
    last_recognition_attempt_at: datetime | None = None
    last_recognition_error: str | None = None

    background_tasks: list = field(default_factory=list)
