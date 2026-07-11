# OwnTone setup

OwnTone is the AirPlay-sending engine this backend drives via its JSON API — it's a
separate system service, not something this Python app implements itself.

## 1. System prerequisites

Building `shazamio`'s Rust extension (`shazamio-core`) needs these apt packages
first (confirmed empirically on this dev machine — `pip install shazamio` fails
without them, missing `pkg-config` for the `alsa-sys` crate's build script):

```
sudo apt update
sudo apt install pkg-config libasound2-dev
```

This alone isn't enough on this machine's system Python (3.14) — `shazamio-core`
has no prebuilt wheel for it and the from-source build segfaults on import (PyO3
version predates 3.14 ABI support). The project's venv must be built on Python
3.12 via pyenv instead — see `README.md` section 2 for the full pyenv setup; this
is unrelated to OwnTone itself, just flagging it here so it isn't missed.

## 2. Install OwnTone

```
sudo apt update
sudo apt install owntone
```

If `apt-cache policy owntone` shows nothing, run `sudo apt update` first (universe
repo may not have been indexed yet) before assuming the package is unavailable.

## 3. Permissions

Make sure the OwnTone service user and whoever runs the Python backend can both
read/write the FIFO — either add both to a shared group, or run both as the same
user in dev.

## 4. Create the pipe library entry

```
sudo mkdir -p /var/lib/owntone/library
sudo mkfifo /var/lib/owntone/library/vinyl.pipe
```

The filename must end in `.pipe` — that's how OwnTone recognizes it as a live pipe
source instead of a static library file. This path must match `FIFO_PATH` in `.env`.

## 5. Configure `/etc/owntone.conf`

Confirm (add if missing) a `library` stanza pointing at that directory:

```
library {
  directories = { "/var/lib/owntone/library" }
}
```

Confirm the JSON API is reachable on the default port 3689 (no separate "enable"
flag expected in recent versions, but verify against this installed version).

## 6. Restart and verify

```
sudo systemctl restart owntone
journalctl -u owntone -f      # confirm it scans the library and finds the pipe
curl http://localhost:3689/api/outputs
```

## 7. Find the pipe track's library id

Before `resolve_pipe_track_uri()` in `app/owntone/client.py` can be trusted, manually
confirm the search query it uses actually finds the pipe track:

```
curl "http://localhost:3689/api/search?type=track&query=vinyl"
```

Adjust `OWNTONE_PIPE_TRACK_QUERY` in `.env` (or the query logic itself) if this
doesn't return the expected track.

## Known caveats to test for

- GitHub issue #1358: now-playing metadata has been reported to sometimes not
  refresh for subsequent tracks on pipe sources in some setups. Explicitly verify
  this works across a track change once the full app is running.
- Sonos/AirPlay 2 specifics (PIN pairing, historical volume/403 issues seen in
  OwnTone's issue tracker) can only be confirmed once the real Sonos device is
  reachable on the LAN.
