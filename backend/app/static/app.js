const POLL_INTERVAL_MS = 3000;

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok && res.status !== 204) {
    throw new Error(`${options?.method || "GET"} ${url} -> ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

function renderStatus(status) {
  const list = document.getElementById("status-list");
  const rows = [
    ["Capture", status.capture_alive],
    ["Current device", status.current_device, true],
    ["AirPlay stream (FIFO)", status.fifo_connected],
    ["OwnTone reachable", status.owntone_reachable],
    ["Dropped audio chunks", status.capture_dropped_chunks, true],
    ["Last recognition error", status.last_recognition_error || "none", true],
  ];
  list.innerHTML = rows
    .map(([label, value, isText]) => {
      if (isText) {
        return `<li><span>${label}</span><span>${value}</span></li>`;
      }
      const cls = value ? "ok" : "bad";
      return `<li><span>${label}</span><span><span class="dot ${cls}"></span>${value ? "OK" : "down"}</span></li>`;
    })
    .join("");
}

function renderNowPlaying(nowPlaying) {
  const el = document.getElementById("now-playing-content");
  if (!nowPlaying.has_match) {
    el.innerHTML = `<p class="muted">Nothing recognized yet.</p>`;
    return;
  }
  const artwork = nowPlaying.artwork_url
    ? `<img src="${nowPlaying.artwork_url}" alt="">`
    : "";
  el.innerHTML = `
    ${artwork}
    <div>
      <div class="now-playing-title">${nowPlaying.title}</div>
      <div class="muted">${nowPlaying.artist}</div>
    </div>
  `;
}

let deviceSelectDirty = false;

function renderDevices(data) {
  const select = document.getElementById("device-select");
  if (deviceSelectDirty) return; // don't clobber a pending user selection
  select.innerHTML = data.devices
    .map(
      (d) =>
        `<option value="${d.device_string}" ${d.device_string === data.current_device ? "selected" : ""}>${d.description}</option>`
    )
    .join("");
}

let outputsDirty = false;

function renderOutputs(outputs) {
  const list = document.getElementById("outputs-list");
  if (outputsDirty) return;
  list.innerHTML = outputs
    .map(
      (o) => `
      <li>
        <label>
          <input type="checkbox" value="${o.id}" ${o.selected ? "checked" : ""}>
          ${o.name} <span class="muted">(${o.type})</span>
        </label>
      </li>`
    )
    .join("");
}

async function refresh() {
  try {
    const [status, nowPlaying, devices, outputs] = await Promise.all([
      fetchJSON("/api/status"),
      fetchJSON("/api/now-playing"),
      fetchJSON("/api/audio/devices"),
      fetchJSON("/api/outputs"),
    ]);
    renderStatus(status);
    renderNowPlaying(nowPlaying);
    renderDevices(devices);
    renderOutputs(outputs);
  } catch (err) {
    console.error("refresh failed", err);
  }
}

document.getElementById("device-select").addEventListener("change", () => {
  deviceSelectDirty = true;
});

document.getElementById("device-apply").addEventListener("click", async () => {
  const device = document.getElementById("device-select").value;
  await fetchJSON("/api/audio/device", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device }),
  });
  deviceSelectDirty = false;
});

document.getElementById("outputs-list").addEventListener("change", () => {
  outputsDirty = true;
});

document.getElementById("outputs-apply").addEventListener("click", async () => {
  const ids = Array.from(
    document.querySelectorAll('#outputs-list input[type="checkbox"]:checked')
  ).map((cb) => cb.value);
  await fetchJSON("/api/outputs", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ output_ids: ids }),
  });
  outputsDirty = false;
});

document.getElementById("playback-start").addEventListener("click", () => {
  fetchJSON("/api/playback/start", { method: "POST" });
});

document.getElementById("playback-stop").addEventListener("click", () => {
  fetchJSON("/api/playback/stop", { method: "POST" });
});

refresh();
setInterval(refresh, POLL_INTERVAL_MS);
