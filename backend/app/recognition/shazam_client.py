import logging
from dataclasses import dataclass

from shazamio import Shazam

logger = logging.getLogger(__name__)


@dataclass
class RecognizedTrack:
    title: str
    artist: str
    artwork_url: str | None = None


class ShazamClient:
    """Wraps a single shared `shazamio.Shazam()` instance (construction is cheap but
    reused across polls rather than recreated each cycle).

    NOTE: the exact result dict shape assumed here — `result["track"]["title"]`,
    `["subtitle"]`, and `["images"]["coverart"]`, matching Shazam's known public API
    shape — plus whether an in-memory WAV byte buffer is accepted as-is, are both
    unconfirmed from ShazamIO's docs. Verify with `scripts/shazam_probe.py` against a
    real snippet before trusting this in production, and adjust the parsing below if
    the real shape differs."""

    def __init__(self) -> None:
        self._shazam = Shazam()

    async def recognize_pcm(self, wav_bytes: bytes) -> RecognizedTrack | None:
        result = await self._shazam.recognize(wav_bytes)
        track = result.get("track")
        if not track:
            return None
        title = track.get("title")
        artist = track.get("subtitle")
        if not title or not artist:
            logger.warning("unexpected ShazamIO result shape: %r", result)
            return None
        artwork_url = track.get("images", {}).get("coverart")
        return RecognizedTrack(title=title, artist=artist, artwork_url=artwork_url)
