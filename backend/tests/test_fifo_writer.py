import asyncio
import os
import types

import pytest

from app.audio.fifo_writer import FifoWriter
from app.config import Settings


def _make_settings(path: str) -> Settings:
    return Settings(
        fifo_path=path,
        fifo_reconnect_interval_seconds=0.02,
        fifo_reconnect_max_backoff_seconds=0.05,
    )


@pytest.mark.asyncio
async def test_connects_once_reader_attaches_and_delivers_chunks(tmp_path):
    fifo_path = str(tmp_path / "test.pipe")
    os.mkfifo(fifo_path)

    state = types.SimpleNamespace(fifo_connected=False)
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    writer = FifoWriter(fifo_path, _make_settings(fifo_path))
    writer_task = asyncio.create_task(writer.run(queue, state))

    # Writer retries with ENXIO until a reader attaches — attach one now.
    read_fd = await asyncio.to_thread(os.open, fifo_path, os.O_RDONLY)
    try:
        await queue.put(b"hello")

        async def read_expected() -> bytes:
            while True:
                data = await asyncio.to_thread(os.read, read_fd, 1024)
                if data:
                    return data
                await asyncio.sleep(0.01)

        received = await asyncio.wait_for(read_expected(), timeout=2)
        assert received == b"hello"
        assert state.fifo_connected is True
    finally:
        writer_task.cancel()
        await asyncio.gather(writer_task, return_exceptions=True)
        os.close(read_fd)


@pytest.mark.asyncio
async def test_reconnects_after_reader_goes_away(tmp_path):
    fifo_path = str(tmp_path / "test.pipe")
    os.mkfifo(fifo_path)

    state = types.SimpleNamespace(fifo_connected=False)
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    writer = FifoWriter(fifo_path, _make_settings(fifo_path))
    writer_task = asyncio.create_task(writer.run(queue, state))

    read_fd = await asyncio.to_thread(os.open, fifo_path, os.O_RDONLY)
    await queue.put(b"x")
    await asyncio.to_thread(os.read, read_fd, 1024)
    assert state.fifo_connected is True

    os.close(read_fd)  # reader disappears

    # Writer's next write should fail (EPIPE/BrokenPipeError) and it should mark
    # itself disconnected, then reconnect once a new reader attaches.
    for _ in range(50):
        await queue.put(b"y")
        if state.fifo_connected is False:
            break
        await asyncio.sleep(0.02)
    assert state.fifo_connected is False

    read_fd2 = await asyncio.to_thread(os.open, fifo_path, os.O_RDONLY)
    try:
        async def read_expected() -> bytes:
            while True:
                data = await asyncio.to_thread(os.read, read_fd2, 1024)
                if data:
                    return data
                await asyncio.sleep(0.01)

        await asyncio.wait_for(read_expected(), timeout=2)
        assert state.fifo_connected is True
    finally:
        writer_task.cancel()
        await asyncio.gather(writer_task, return_exceptions=True)
        os.close(read_fd2)
