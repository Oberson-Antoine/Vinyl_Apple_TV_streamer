import asyncio
import logging
from datetime import datetime, timezone

from app.audio.wav import pcm_to_wav_bytes
from app.config import Settings
from app.owntone.exceptions import OwnToneUnavailable
from app.recognition.shazam_client import ShazamClient
from app.state import AppState, NowPlaying

logger = logging.getLogger(__name__)

# Below this, a snippet is probably just silence/startup — not worth a Shazam call.
MIN_SNAPSHOT_SECONDS = 3.0


async def run(state: AppState, settings: Settings, shazam: ShazamClient) -> None:
    """Every `recognize_poll_interval_seconds`, snapshots recent audio from the ring
    buffer, asks ShazamIO what it is, and — only on a change — pushes the result to
    OwnTone as now-playing metadata. ShazamIO is an unofficial/reverse-engineered
    client with no documented rate limits or SLA, so every failure mode here is
    caught and logged rather than allowed to crash the loop."""
    while True:
        await asyncio.sleep(settings.recognize_poll_interval_seconds)
        await _attempt(state, settings, shazam)


async def _attempt(state: AppState, settings: Settings, shazam: ShazamClient) -> None:
    state.last_recognition_attempt_at = datetime.now(timezone.utc)

    pcm = state.ring_buffer.snapshot(
        settings.recognize_snapshot_seconds, settings.bytes_per_second
    )
    if len(pcm) < MIN_SNAPSHOT_SECONDS * settings.bytes_per_second:
        return  # not enough audio buffered yet (e.g. just started)

    try:
        wav_bytes = pcm_to_wav_bytes(
            pcm,
            channels=settings.channels,
            sample_width=settings.sample_width,
            framerate=settings.sample_rate,
        )
        track = await shazam.recognize_pcm(wav_bytes)
    except Exception as exc:
        state.last_recognition_error = str(exc)
        logger.warning("recognition attempt failed", exc_info=exc)
        return

    state.last_recognition_error = None

    if track is None:
        state.consecutive_no_match += 1
        if state.consecutive_no_match >= settings.recognize_no_match_clear_threshold:
            state.now_playing = None
        return

    state.consecutive_no_match = 0
    changed = (
        state.now_playing is None
        or state.now_playing.title != track.title
        or state.now_playing.artist != track.artist
    )
    state.now_playing = NowPlaying(
        title=track.title,
        artist=track.artist,
        artwork_url=track.artwork_url,
        recognized_at=datetime.now(timezone.utc),
    )

    if changed:
        try:
            await state.owntone_client.set_now_playing(
                track.title, track.artist, track.artwork_url
            )
        except OwnToneUnavailable as exc:
            logger.warning("failed to push now-playing to OwnTone: %s", exc)
