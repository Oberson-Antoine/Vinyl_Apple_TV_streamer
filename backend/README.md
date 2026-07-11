# Vinyl-to-AirPlay backend

Captures line-in audio from a USB turntable interface, streams it continuously to
AirPlay receivers (e.g. a Sonos speaker) via [OwnTone](https://github.com/owntone/owntone-server),
periodically identifies the playing track with ShazamIO, and pushes the result to
OwnTone as now-playing metadata. Exposes a small REST API for output selection and
status, for a future web frontend to consume.

See `../` plan/context for the full architecture writeup.

## Setup

### 1. System prerequisites

```
sudo apt update
sudo apt install pkg-config libasound2-dev  # needed to build shazamio's Rust extension
```

Then follow `docs/owntone-setup.md` to install and configure OwnTone.

### 2. Python version — must be 3.12 or 3.13, NOT the system Python

`shazamio`'s native dependency (`shazamio-core`, a Rust/PyO3 extension) only ships
working prebuilt wheels for Python 3.9–3.13. On this dev machine the system Python is
3.14, which has no prebuilt wheel — `pip install shazamio` falls back to compiling
`shazamio-core` from source, which "succeeds" but produces a binary that **segfaults
on import** (confirmed empirically) because it's built against a PyO3 version that
predates real 3.14 ABI support. There is no fix at the apt-package level for this —
it needs an actual different Python version.

This project uses [pyenv](https://github.com/pyenv/pyenv) to get Python 3.12
without touching the system Python:

```
curl -fsSL https://pyenv.run | bash
# add pyenv to your shell per its installer output, or just for this session:
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"

# pyenv compiles Python from source, so it needs these build headers first:
sudo apt install build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev libncurses-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev

pyenv install 3.12.13   # matches .python-version; takes a few minutes to compile
```

### 3. Python environment

```
cd backend
~/.pyenv/versions/3.12.13/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements.txt for a runtime-only install
cp .env.example .env
```

Edit `.env` for your machine — in particular confirm `ALSA_DEVICE` with `arecord -l`
(see the by-ear verification step in the plan before trusting the default).

### 4. Verify ShazamIO's result shape before relying on it

```
python scripts/shazam_probe.py path/to/known_song.wav
```

Confirms the actual result dict shape (title/artist/artwork key paths) — adjust
`app/recognition/shazam_client.py` if it differs from what's assumed there.

## Running

```
uvicorn app.main:app --reload
```

## Testing

```
pytest
```

Note: tests for `app/audio/*` don't require `shazamio` to be installed; the app as a
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
