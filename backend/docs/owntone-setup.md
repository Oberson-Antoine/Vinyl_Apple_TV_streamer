# OwnTone setup

OwnTone is the AirPlay-sending engine this backend drives via its JSON API — it's a
separate system service, not something this Python app implements itself.

## 1. Try apt first

```
sudo apt update
sudo apt install owntone
```

This may just work — but don't assume it will. On the x86_64 Ubuntu 26.04 dev
machine this project was built on, **no working install path existed via apt or
prebuilt `.deb`**:
- `owntone` isn't in Ubuntu 26.04's repos at all (confirmed via `apt-cache search`
  after a full `apt update`, universe enabled).
- The maintainer's prebuilt Debian packages
  (https://github.com/owntone/owntone-debian/releases) come in `bookworm`/`trixie`/
  `forky` builds. Both `trixie` and `forky` failed to install on this box —
  Ubuntu 26.04's ffmpeg libraries (`libavcodec62`) sit in a version gap between
  what `trixie` (`libavcodec61`, older) and `forky` (`libavutil` slightly newer)
  require. Neither lines up.

If `apt install owntone` fails or pulls unsatisfiable dependencies on your target
machine too, skip straight to building from source below — don't waste time
chasing `.deb` version mismatches, they don't resolve themselves.

**Raspberry Pi note:** those prebuilt `.deb` releases are `amd64` only anyway, so
they're not an option on Pi hardware regardless of the above. Building from source
(next section) is architecture-agnostic — it compiles against whatever's actually
installed on the Pi — and is the recommended path there from the start.

## 2. Build from source (the path that actually worked)

Build dependencies (Debian/Ubuntu package list from the project's own
`docs/building.md`, confirmed working):

```
sudo apt update
sudo apt install -y build-essential git autotools-dev autoconf automake libtool \
  gettext gawk gperf bison flex libconfuse-dev libunistring-dev libsqlite3-dev \
  libavcodec-dev libavformat-dev libavfilter-dev libswscale-dev libavutil-dev \
  libasound2-dev libxml2-dev libgcrypt20-dev libavahi-client-dev zlib1g-dev \
  libevent-dev libplist-dev libsodium-dev libjson-c-dev libwebsockets-dev \
  libcurl4-openssl-dev libprotobuf-c-dev
```

Build and install:

```
cd /tmp
git clone https://github.com/owntone/owntone-server.git
cd owntone-server
autoreconf -i
./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --enable-install-user
make
sudo make install
```

`--enable-install-user` makes `make install` do everything a `.deb` would have:
create the `owntone` system user/group, install the systemd unit to
`/etc/systemd/system/owntone.service`, and drop a default config at
`/etc/owntone.conf`. Confirmed this build's `configure` step auto-detects the
installed ffmpeg/libav API via feature checks rather than requiring an exact
version — this is exactly why building from source sidesteps the `.deb`
soname-mismatch problem above.

Building takes a few minutes on typical dev hardware; **on a Raspberry Pi (much
slower CPU), budget significantly longer** — possibly 20-30+ minutes for `make`.

**Also install `avahi-daemon` (a runtime dependency, not just the `libavahi-client-dev`
headers above)** — OwnTone needs it running for AirPlay/mDNS device discovery, and
its systemd unit fails to start entirely without it (`Unit avahi-daemon.socket not
found`). This was already present by default on the original Ubuntu desktop dev
machine, so it went unnoticed until a minimal Debian-based Pi image (no desktop
extras) hit it directly:

```
sudo apt install -y avahi-daemon
sudo systemctl enable --now avahi-daemon
```

## 3. Set up the pipe library directory and permissions

Replace `sounox` below with whichever user actually runs the Python backend
service on this machine (matches `User=`/`Group=` in
`deploy/vinyl-streamer.service`).

```
sudo mkdir -p /var/lib/owntone/library
sudo chown <backend-user>:owntone /var/lib/owntone/library
sudo chmod 2775 /var/lib/owntone/library   # setgid: new files inherit group "owntone"

mkfifo /var/lib/owntone/library/vinyl.pipe
chmod 664 /var/lib/owntone/library/vinyl.pipe
```

The setgid bit means the FIFO automatically comes out owned by `<backend-user>:owntone`
with no extra `chgrp` needed — the backend user (owner) can write, the `owntone`
service user (via group membership, confirmed already a member of its own primary
group `owntone`) can read.

The FIFO's filename must end in `.pipe` — that's how OwnTone recognizes it as a
live pipe source instead of a static library file. This path must match
`FIFO_PATH` in `.env`.

## 4. Configure `/etc/owntone.conf`

Point the library at that directory (the installed default is `/srv/music`):

```
sudo sed -i 's|directories = { "/srv/music" }|directories = { "/var/lib/owntone/library" }|' /etc/owntone.conf
```

Confirm the JSON API is reachable on the default port 3689 (`library.port`, same
port serves DAAP and the JSON API — no separate "enable" flag needed).

## 5. Start and verify

First time (registers it to start on boot too):

```
sudo systemctl enable --now owntone
sudo systemctl status owntone --no-pager
curl http://localhost:3689/api/outputs
```

After any later config change, use `sudo systemctl restart owntone` instead.

The library scan happens automatically on start — check it found the pipe:

```
curl "http://localhost:3689/api/search?type=track&query=vinyl"
```

This should return one track with `"data_kind": "pipe"` and
`"path": "/var/lib/owntone/library/vinyl.pipe"`. If it doesn't, double check step 3's
permissions (`owntone` couldn't read the directory) before anything else.

Adjust `OWNTONE_PIPE_TRACK_QUERY` in `.env` (or the query logic in
`app/owntone/client.py`) if a different query is needed to find your pipe track.

## Known caveats confirmed during development

- Repeatedly calling the "start playback" endpoint without clearing the queue first
  used to pile up duplicate queue entries pointing at the same pipe track — fixed in
  `OwnToneClient.start_pipe_playback()` (clears the queue before re-adding).
- Right after a queue clear+add, the player briefly reports `state: "pause"` for a
  second or two before settling into `"play"` on its own — not a bug, just don't
  read the state immediately after starting playback.
- GitHub issue #1358 (now-playing metadata not refreshing for subsequent pipe
  tracks) was **not** observed as a problem in practice — metadata pushes via
  `PUT /api/queue/items/now_playing` were confirmed reflected correctly in testing.
- AirPlay 2 device discovery and playback (including to real Sonos speakers) worked
  without any PIN pairing or extra configuration once the library/pipe setup above
  was correct.
