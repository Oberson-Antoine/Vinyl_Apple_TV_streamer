"""Manual verification script — NOT part of the app.

Feeds a real audio file to ShazamIO and prints the raw result, so we can confirm
the actual result shape (title/artist/artwork key paths) before trusting the
parsing logic in app/recognition/shazam_client.py.

Usage:
    python scripts/shazam_probe.py path/to/known_song.wav
"""

import asyncio
import json
import sys

from shazamio import Shazam


async def main(path: str) -> None:
    with open(path, "rb") as f:
        data = f.read()

    shazam = Shazam()
    result = await shazam.recognize(data)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} <path-to-audio-file>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
