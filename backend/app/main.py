import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routers import audio, outputs, playback, status
from app.audio.capture import AudioCapture
from app.audio.ring_buffer import RingBuffer
from app.config import settings
from app.owntone.client import OwnToneClient
from app.recognition import recognizer
from app.recognition.shazam_client import ShazamClient
from app.state import AppState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _supervise(name: str, coro_fn, *args) -> None:
    """Restarts a background task with a fixed backoff if it ever raises past its own
    internal error handling — a bug here should never silently kill recognition or
    capture for the rest of the process lifetime."""
    while True:
        try:
            await coro_fn(*args)
            return  # coro_fn returned normally (shouldn't happen for our loops)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("background task %r crashed, restarting in 5s", name)
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ring_buffer = RingBuffer(settings.ring_buffer_seconds, settings.bytes_per_second)
    owntone_client = OwnToneClient(settings.owntone_base_url, settings.owntone_http_timeout_seconds)
    state = AppState(
        ring_buffer=ring_buffer,
        owntone_client=owntone_client,
        current_alsa_device=settings.alsa_device,
    )
    app.state.app_state = state

    shazam = ShazamClient()
    tasks = [
        asyncio.create_task(
            _supervise("capture", AudioCapture().run, state, settings), name="capture"
        ),
        asyncio.create_task(
            _supervise("recognizer", recognizer.run, state, settings, shazam),
            name="recognizer",
        ),
    ]
    state.background_tasks = tasks

    yield

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await owntone_client.aclose()


app = FastAPI(title="Vinyl AirPlay Streamer", lifespan=lifespan)
app.include_router(outputs.router, prefix="/api/outputs", tags=["outputs"])
app.include_router(playback.router, prefix="/api/playback", tags=["playback"])
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])

# Mounted last so it acts as a fallback and doesn't shadow the /api/* routes above
# (Starlette matches routes in registration order).
app.mount(
    "/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static"
)
