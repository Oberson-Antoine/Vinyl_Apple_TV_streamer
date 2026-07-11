import asyncio
import errno
import fcntl
import logging
import os

from app.config import Settings
from app.state import AppState

logger = logging.getLogger(__name__)


class FifoWriter:
    """Streams PCM chunks from a queue into OwnTone's pipe FIFO.

    Two hazards this exists to handle:
    - Opening a FIFO's write end blocks until a reader is attached. We open it
      O_NONBLOCK instead, which raises ENXIO immediately if OwnTone hasn't opened the
      read end yet, so we can retry on a timer instead of hanging the event loop.
    - Even once connected, a blocking write() can stall indefinitely if OwnTone pauses
      reading (e.g. mid-restart). Writes run in a thread via asyncio.to_thread so they
      never stall the event loop that's also driving audio capture and the HTTP API.
    """

    def __init__(self, path: str, settings: Settings) -> None:
        self._path = path
        self._settings = settings

    async def run(self, queue: asyncio.Queue[bytes], state: AppState) -> None:
        while True:
            fd = await self._connect(state)
            state.fifo_connected = True
            logger.info("FIFO connected: %s", self._path)
            try:
                await self._write_loop(fd, queue)
            except (BrokenPipeError, OSError) as exc:
                logger.warning("FIFO write failed, reconnecting: %s", exc)
            finally:
                state.fifo_connected = False
                os.close(fd)

    async def _connect(self, state: AppState) -> int:
        delay = self._settings.fifo_reconnect_interval_seconds
        while True:
            try:
                fd = os.open(self._path, os.O_WRONLY | os.O_NONBLOCK)
                flags = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
                return fd
            except OSError as exc:
                if exc.errno != errno.ENXIO:
                    logger.warning("unexpected error opening FIFO %s: %s", self._path, exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._settings.fifo_reconnect_max_backoff_seconds)

    async def _write_loop(self, fd: int, queue: asyncio.Queue[bytes]) -> None:
        while True:
            chunk = await queue.get()
            await asyncio.to_thread(os.write, fd, chunk)
