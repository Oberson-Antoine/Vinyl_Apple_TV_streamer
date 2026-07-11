# Vinyl-to-AirPlay backend

Captures line-in audio from a USB turntable interface, streams it continuously to
AirPlay receivers (e.g. a Sonos speaker) via [OwnTone](https://github.com/owntone/owntone-server),
periodically identifies the playing track with ShazamIO, and pushes the result to
OwnTone as now-playing metadata. Includes a small web UI (input/output device
selection, live status) and REST API.

This has been built and verified end-to-end on a dev machine (Ubuntu 26.04 x86_64)
against a real Sonos speaker. The steps below are what actually worked there —
including a couple of dead ends worth knowing about before you hit them again on
different hardware (e.g. the eventual Raspberry Pi deployment).

**Raspberry Pi note:** everything below is architecture-agnostic (no step assumes
x86_64) except where called out. Expect apt package availability to differ on
Raspberry Pi OS vs. this dev machine's Ubuntu 26.04 — re-check each "try apt first"
step rather than assuming the same result, and expect anything built from source
(Python, OwnTone) to take substantially longer on a Pi's CPU.

## Deployment order

1. System prerequisites (apt packages for building `shazamio`)
2. Python 3.12/3.13 via pyenv (system Python is very likely too new/incompatible)
3. Project venv + dependencies
4. OwnTone install + config (separate doc: `docs/owntone-setup.md`)
5. Verify ShazamIO's result shape
6. Run manually once to confirm everything works
7. Install both services (`owntone` + this app) via systemd so they start on boot

## 1. System prerequisites

```
sudo apt update
sudo apt install pkg-config libasound2-dev
```

Needed to build `shazamio`'s Rust extension (`shazamio-core`) — without these, the
build fails with a `pkg-config`-not-found error from the `alsa-sys` crate. Confirmed
empirically, not a guess.

## 2. Python version — must be 3.12 or 3.13, NOT necessarily the system Python

`shazamio-core` only ships working prebuilt wheels for Python 3.9–3.13. On this dev
machine the system Python was 3.14, which has no prebuilt wheel — `pip install
shazamio` fell back to compiling `shazamio-core` from source, which *appeared* to
succeed but produced a binary that **segfaults on import** (confirmed empirically),
because it's built against a PyO3 version that predates real 3.14 ABI support.
There's no apt-package-level fix for this; it needs an actual different Python
version. **Check your target machine's system Python version first** — if it's
already 3.12 or 3.13, you can likely skip pyenv entirely and use it directly.

If not, get Python 3.12 via [pyenv](https://github.com/pyenv/pyenv) without
touching the system Python:

```
curl -fsSL https://pyenv.run | bash
# add pyenv to your shell per its installer output, or just for this session:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

# pyenv compiles Python from source, so it needs these build headers first:
sudo apt install build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev libncurses-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev

pyenv install 3.12.13   # matches .python-version; takes a few minutes on a desktop CPU,
                        # significantly longer on a Raspberry Pi — let it run
```

## 3. Python environment

```
cd backend
~/.pyenv/versions/3.12.13/bin/python3.12 -m venv .venv   # or your system python3.12/3.13
source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements.txt for a runtime-only install
cp .env.example .env
```

Edit `.env` for this machine:
- `ALSA_DEVICE` — confirm with `arecord -l` (device numbering/naming can differ per
  machine — don't assume the same `plughw:CARD=...` string as another install).
  Verify by ear: record a short clip while playing known audio into the interface
  and listen back, since multiple capture devices are often present.
- Everything else in `.env.example` has working defaults, but review them.

## 4. Install and configure OwnTone

See **`docs/owntone-setup.md`** — this is a separate system service (not part of
this Python app) with its own install path. Short version: try `sudo apt install
owntone` first, but be ready for it to not be available or to have unsatisfiable
dependencies (both happened on the dev machine) — the doc has the full
build-from-source fallback that's confirmed to work, plus the exact FIFO
permission setup this app's `.env` (`FIFO_PATH`) expects.

## 5. Verify ShazamIO's result shape before relying on it

```
python scripts/shazam_probe.py path/to/known_song.wav
```

Prints the raw result dict — confirms the actual title/artist/artwork key paths
match what `app/recognition/shazam_client.py` assumes (already confirmed to match
on the dev machine, but ShazamIO is an unofficial/reverse-engineered client, so
re-verify if anything looks off after a `shazamio` version bump).

## 6. Run manually to confirm everything works

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://<host>:8000/` — the web UI shows live status, lets you pick the input
device and AirPlay output(s), and start/stop streaming. Confirm:
- `/api/status` shows `capture_alive`, `fifo_connected`, and `owntone_reachable`
  all `true`.
- Selecting a real AirPlay output and starting playback produces actual audio.
- Playing a known song gets recognized within `RECOGNIZE_POLL_INTERVAL_SECONDS`
  and updates the now-playing display.

Only move on to the systemd setup once this manual run works — it's much easier to
debug interactively than through `journalctl`.

## 7. Run as systemd services (start automatically on boot)

Both `owntone` and this app should be system-level services (not tied to any login
session), so they come up on power-on with nobody logged in — the actual goal for
the Raspberry Pi deployment.

`owntone.service` is installed automatically by `make install` in
`docs/owntone-setup.md` (or by the apt package, if that worked for you). This app's
unit is `deploy/vinyl-streamer.service`:

```
[Unit]
Description=Vinyl AirPlay Streamer backend
After=network-online.target sound.target owntone.service
Wants=network-online.target owntone.service

[Service]
Type=simple
User=sounox
Group=sounox
WorkingDirectory=/home/sounox/Vinyl_Apple_TV_streamer/backend
ExecStart=/home/sounox/Vinyl_Apple_TV_streamer/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Before installing on a new machine, edit `User=`/`Group=`/`WorkingDirectory=`/
`ExecStart=`** to match that machine's actual username and where this repo and its
`.venv` live — the checked-in file hardcodes the dev machine's values (`sounox`,
`/home/sounox/...`).

It's ordered after OwnTone (`After=`) but only *wants* it (`Wants=`, not
`Requires=`) — this app already degrades gracefully (`owntone_reachable: false`,
logged and retried, never crashes) if OwnTone isn't up yet, matching how every
other dependency failure (arecord dying, FIFO disconnecting) is handled internally.

```
sudo cp deploy/vinyl-streamer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vinyl-streamer
sudo systemctl status vinyl-streamer --no-pager
```

Confirm it actually works the same way step 6 did, just now via the service:

```
curl http://localhost:8000/api/status
```

A real reboot (once convenient — this stops everything else running on the
machine) is the final proof both `owntone` and `vinyl-streamer` come up
unattended; the `enable` step above registers them for it either way.

## Testing

```
pytest
```

Tests for `app/audio/*` don't require `shazamio` to be installed; the app as a
whole (`app.main`) does, since the recognition loop is wired into startup.

## REST API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/outputs` | List AirPlay outputs (proxies OwnTone) |
| PUT | `/api/outputs` | Select active outputs `{"output_ids": [...]}` |
| PUT | `/api/outputs/{id}` | Toggle/set volume on one output |
| POST | `/api/playback/start` | Start streaming the pipe source through OwnTone |
| POST | `/api/playback/stop` | Stop playback |
| GET | `/api/now-playing` | Current recognized title/artist/artwork |
| GET | `/api/status` | Capture/FIFO/OwnTone/recognition health |
| GET | `/api/audio/devices` | List detected ALSA capture devices + current selection |
| POST | `/api/audio/device` | Switch the live capture device `{"device": "plughw:..."}` |

Web UI (same host/port) is served at `/`.
