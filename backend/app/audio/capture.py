import asyncio
import logging
from datetime import datetime, timezone

from app.audio.fifo_writer import FifoWriter
from app.config import Settings
from app.state import AppState

logger = logging.getLogger(__name__)


class AudioCapture:
    """Owns the ALSA capture device exclusively via a single long-running `arecord`
    subprocess (USB audio devices are exclusive-access, so we can't run a second
    concurrent arecord against the same hardware). Reads its stdout, frame-aligns the
    bytes, and tees each chunk to the ring buffer (recognition) and a FIFO writer
    (OwnTone streaming)."""

    async def run(self, state: AppState, settings: Settings) -> None:
        """Supervising loop: (re)spawns arecord and restarts with backoff whenever it
        dies (crash, USB unplug) — never lets a capture failure kill the process."""
        backoff_schedule = settings.capture_restart_backoff_seconds
        attempt = 0
        while True:
            try:
                await self._run_once(state, settings)
            except Exception:
                logger.exception("capture loop crashed, restarting")
            state.capture_alive = False
            delay = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
            attempt += 1
            await asyncio.sleep(delay)

    async def _run_once(self, state: AppState, settings: Settings) -> None:
        """One arecord lifecycle: spawn it, its own FIFO writer + queue, run until
        arecord exits or errors, then clean up."""
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=settings.fifo_queue_maxsize)
        fifo_writer = FifoWriter(settings.fifo_path, settings)
        fifo_task = asyncio.create_task(fifo_writer.run(queue, state))

        proc = await asyncio.create_subprocess_exec(
            "arecord",
            "-D", settings.alsa_device,
            "-f", "S16_LE",
            "-c", str(settings.channels),
            "-r", str(settings.sample_rate),
            "-t", "raw",
            "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        state.capture_alive = True
        logger.info("arecord started (pid=%s, device=%s)", proc.pid, settings.alsa_device)

        stderr_task = asyncio.create_task(self._drain_stderr(proc))
        try:
            await self._read_loop(proc, queue, state, settings)
        finally:
            fifo_task.cancel()
            stderr_task.cancel()
            await asyncio.gather(fifo_task, stderr_task, return_exceptions=True)
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    async def _read_loop(
        self,
        proc: asyncio.subprocess.Process,
        queue: asyncio.Queue[bytes],
        state: AppState,
        settings: Settings,
    ) -> None:
        """Reads raw PCM from arecord's stdout and forwards only whole audio frames
        downstream. `StreamReader.read(n)` can return a chunk not aligned to the
        frame size (channels * sample_width bytes) — forwarding misaligned bytes
        causes channel-swap/clicking artifacts, so leftover bytes are carried over to
        the next read instead."""
        assert proc.stdout is not None
        frame_size = settings.frame_size
        leftover = b""

        while True:
            data = await proc.stdout.read(settings.capture_chunk_bytes)
            if not data:
                if proc.returncode is not None:
                    logger.warning("arecord exited with code %s", proc.returncode)
                else:
                    logger.warning("arecord stdout closed unexpectedly")
                return

            data = leftover + data
            usable_len = len(data) - (len(data) % frame_size)
            leftover = data[usable_len:]
            chunk = data[:usable_len]
            if not chunk:
                continue

            state.ring_buffer.append(chunk)
            state.last_capture_chunk_at = datetime.now(timezone.utc)

            try:
                queue.put_nowait(chunk)
            except asyncio.QueueFull:
                # Prefer dropping stale audio over blocking capture or growing
                # memory unboundedly — a brief AirPlay glitch is fine, stalling
                # the capture loop is not.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait(chunk)
                state.capture_dropped_chunks += 1

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
        """Keeps arecord's stderr pipe from filling up and stalling the subprocess;
        also surfaces its own diagnostics at debug level."""
        assert proc.stderr is not None
        while True:
            line = await proc.stderr.readline()
            if not line:
                return
            logger.debug("arecord: %s", line.decode(errors="replace").rstrip())
