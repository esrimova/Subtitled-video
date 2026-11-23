const STRINGS = {
  checkFailed: "Could not check the video.",
  running: "Running…",
  cancelled: "Cancelled",
  cancelling: "Cancelling…",
  etaSeconds: "About {s} s left",
  etaMinutes: "About {m} min left",
  linkKind: "Link",
  fileKind: "File",
  lengthUnknown: "Length unknown",
  doneTitle: "Done",
  videoQuality: "Video quality",
  onlyOneQuality: "Only one quality is available.",
  stageNames: {
    download: "Downloading",
    audio: "Extracting audio",
    transcribe: "Transcribing",
    captions: "Building captions"
  }
};

const TOKEN = new URLSearchParams(location.search).get("t");

async function api(path, body) {
  const opts = {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "X-Token": TOKEN,
      "Content-Type": "application/json"
    }
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  try {
    const res = await fetch(path, opts);
    return await res.json();
  } catch {
    return { ok: false, reason: "Could not reach the app." };
  }
}

function fmtTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function fmtEta(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) return "";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) {
    return STRINGS.etaSeconds.replace("{s}", s);
  }
  const m = Math.round(s / 60);
  return STRINGS.etaMinutes.replace("{m}", m);
}