import threading
from collections import deque


class RingBuffer:
    """Holds the last `max_seconds` of raw PCM, fed continuously from the capture
    loop. Independent of the FIFO/OwnTone path so recognition keeps working even if
    streaming is down."""

    def __init__(self, max_seconds: float, bytes_per_second: int) -> None:
        self._max_bytes = int(max_seconds * bytes_per_second)
        self._chunks: deque[bytes] = deque()
        self._total_bytes = 0
        self._lock = threading.Lock()

    def append(self, chunk: bytes) -> None:
        with self._lock:
            self._chunks.append(chunk)
            self._total_bytes += len(chunk)
            while self._total_bytes > self._max_bytes and len(self._chunks) > 1:
                dropped = self._chunks.popleft()
                self._total_bytes -= len(dropped)

    def snapshot(self, seconds: float, bytes_per_second: int) -> bytes:
        """Returns up to the last `seconds` worth of PCM, oldest first."""
        want_bytes = int(seconds * bytes_per_second)
        with self._lock:
            data = b"".join(self._chunks)
        return data[-want_bytes:] if want_bytes < len(data) else data
