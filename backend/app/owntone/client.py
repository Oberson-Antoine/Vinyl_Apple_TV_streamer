import logging
from dataclasses import dataclass

import httpx

from app.owntone.exceptions import OwnToneUnavailable

logger = logging.getLogger(__name__)


@dataclass
class OutputInfo:
    id: str
    name: str
    type: str
    selected: bool
    volume: int


class OwnToneClient:
    """Thin async wrapper around OwnTone's JSON HTTP API
    (https://owntone.github.io/owntone-server/json-api/). Every method raises
    `OwnToneUnavailable` on connection errors/timeouts so callers (the recognizer,
    the REST routers) can distinguish "OwnTone is down" from a real bug."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout_seconds)
        self._pipe_track_uri: str | None = None

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise OwnToneUnavailable(f"OwnTone unreachable: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise OwnToneUnavailable(
                f"OwnTone returned {exc.response.status_code} for {method} {path}"
            ) from exc

    async def health(self) -> bool:
        try:
            await self._request("GET", "/api/outputs")
            return True
        except OwnToneUnavailable:
            return False

    async def get_outputs(self) -> list[OutputInfo]:
        response = await self._request("GET", "/api/outputs")
        payload = response.json()
        return [
            OutputInfo(
                id=str(o["id"]),
                name=o["name"],
                type=o.get("type", ""),
                selected=o.get("selected", False),
                volume=o.get("volume", 0),
            )
            for o in payload.get("outputs", [])
        ]

    async def set_outputs(self, output_ids: list[str]) -> None:
        await self._request("PUT", "/api/outputs/set", json={"outputs": output_ids})

    async def set_output(
        self, output_id: str, *, selected: bool | None = None, volume: int | None = None
    ) -> None:
        body = {}
        if selected is not None:
            body["selected"] = selected
        if volume is not None:
            body["volume"] = volume
        await self._request("PUT", f"/api/outputs/{output_id}", json=body)

    async def resolve_pipe_track_uri(self, query: str) -> str:
        """Finds the library track id for our pipe source, so we know what to pass
        to `/api/queue/items/add`. Cached after the first successful lookup.

        NOTE: the exact search query schema is unconfirmed from docs alone — verify
        against a running OwnTone instance (see docs/owntone-setup.md step 7) and
        adjust the query params here if this doesn't return the expected track."""
        if self._pipe_track_uri is not None:
            return self._pipe_track_uri

        response = await self._request(
            "GET", "/api/search", params={"type": "track", "query": query}
        )
        payload = response.json()
        tracks = payload.get("tracks", {}).get("items", [])
        if not tracks:
            raise OwnToneUnavailable(
                f"no OwnTone library track found matching query={query!r}"
            )
        track_id = tracks[0]["id"]
        self._pipe_track_uri = f"library:track:{track_id}"
        return self._pipe_track_uri

    async def start_pipe_playback(self, query: str) -> None:
        """Clears the queue first — confirmed empirically that repeated calls to
        `/api/queue/items/add` without clearing pile up duplicate queue entries for
        the same pipe track (harmless to playback, but clutters the queue). OwnTone
        auto-re-adds the pipe track right after a clear as long as data is still
        flowing through the FIFO, so this still ends with exactly one queue item."""
        uri = await self.resolve_pipe_track_uri(query)
        await self._request("PUT", "/api/queue/clear")
        await self._request(
            "POST", "/api/queue/items/add", params={"uris": uri, "playback": "start"}
        )

    async def stop_playback(self) -> None:
        await self._request("PUT", "/api/player/stop")

    async def set_now_playing(
        self, title: str, artist: str, artwork_url: str | None = None
    ) -> None:
        params = {"title": title, "artist": artist}
        if artwork_url:
            params["artwork_url"] = artwork_url
        await self._request("PUT", "/api/queue/items/now_playing", params=params)
