let currentKind = null;
let currentNoAudio = false;
let currentPipeline = [];
let currentQualities = [];
let currentKeep = [];
let eventSource = null;

function show(screen) {
  const sections = {
    idle: ["idle-section"],
    checking: ["idle-section", "checking"],
    options: ["idle-section", "options"],
    running: ["running"],
    done: ["done"],
    stopped: ["stopped"]
  };
  const all = ["idle-section", "options", "running", "done", "stopped", "checking"];
  all.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  });
  const toShow = sections[screen] || [];
  toShow.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.hidden = false;
  });
  if (screen === "idle") {
    document.getElementById("source").disabled = false;
    document.getElementById("check-btn").disabled = false;
  } else if (screen === "options") {
    document.getElementById("source").disabled = true;
    document.getElementById("check-btn").disabled = true;
  }
}

function setError(msg) {
  const el = document.getElementById("error");
  if (el) {
    el.textContent = msg;
    el.hidden = !msg;
  }
}

function clearError() {
  setError("");
}

function buildSummary(data) {
  const el = document.getElementById("summary");
  const title = document.createElement("div");
  title.className = "title";
  title.textContent = data.title || "Unknown";
  const meta = document.createElement("div");
  meta.className = "meta";
  const kindLabel = data.kind === "url" ? STRINGS.linkKind : STRINGS.fileKind;
  const dur = data.duration > 0 ? fmtTime(data.duration) : STRINGS.lengthUnknown;
  meta.textContent = `${kindLabel} • ${dur}`;
  el.replaceChildren(title, meta);
}

function renderOutputs(outputs) {
  const container = document.getElementById("outputs");
  container.replaceChildren();
  outputs.forEach(out => {
    const row = document.createElement("div");
    row.className = "output-row";
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = out.id;
    checkbox.disabled = !out.available;
    if (out.id === "video" && out.available) checkbox.checked = true;
    checkbox.addEventListener("change", onOutputChange);
    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(out.label));
    row.appendChild(label);
    if (!out.available && out.note) {
      const note = document.createElement("span");
      note.className = "note";
      note.textContent = out.note;
      row.appendChild(note);
    }
    container.appendChild(row);
  });
}

function updatePlanNotes(notes) {
  const el = document.getElementById("plan-notes");
  el.textContent = notes.join(" ");
}

function updateModelRow(pipeline, keep) {
  const row = document.getElementById("model-row");
  row.hidden = !pipeline.includes("transcribe");
  const qualityRow = document.getElementById("quality-row");
  const qualitySelect = document.getElementById("quality");
  const qualityNote = document.getElementById("quality-note");
  const hasVideo = keep.includes("video") || keep.includes("replay");
  const hasQualities = currentQualities.length > 0;
  qualityRow.hidden = !(hasVideo && hasQualities);
  if (hasVideo && hasQualities) {
    if (currentQualities.length === 1) {
      qualitySelect.disabled = true;
      qualityNote.textContent = STRINGS.onlyOneQuality;
    } else {
      qualitySelect.disabled = false;
      qualityNote.textContent = "";
    }
  }
}

function updateStartBtn() {
  const btn = document.getElementById("start-btn");
  const checkboxes = document.querySelectorAll("#outputs input[type=checkbox]:checked");
  btn.disabled = checkboxes.length === 0;
}

function onOutputChange() {
  const checked = Array.from(document.querySelectorAll("#outputs input[type=checkbox]:checked")).map(c => c.value);
  api("/api/plan", { outputs: checked, no_audio: currentNoAudio, kind: currentKind }).then(res => {
    if (!res.ok) {
      setError(res.reason);
      return;
    }
    clearError();
    currentKeep = res.keep || [];
    updatePlanNotes(res.notes || []);
    updateModelRow(res.pipeline || [], currentKeep);
    currentPipeline = res.pipeline || [];
    updateStartBtn();
  });
}

function buildStages(pipeline) {
  const ul = document.getElementById("stages");
  ul.replaceChildren();
  pipeline.forEach(stageId => {
    const li = document.createElement("li");
    li.className = "pending";
    li.dataset.stage = stageId;
    const status = document.createElement("span");
    status.className = "stage-status";
    const name = document.createElement("span");
    name.className = "stage-name";
    name.textContent = STRINGS.stageNames[stageId] || stageId;
    li.appendChild(status);
    li.appendChild(name);
    ul.appendChild(li);
  });
}

function markStageActive(stageId) {
  const items = document.querySelectorAll("#stages li");
  let found = false;
  items.forEach(li => {
    if (li.dataset.stage === stageId) {
      li.className = "active";
      found = true;
    } else if (!found) {
      li.className = "done";
    } else {
      li.className = "pending";
    }
  });
}

function openEventSource() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/api/events?t=" + TOKEN);
  eventSource.onmessage = e => {
    try {
      const msg = JSON.parse(e.data);
      handleEvent(msg);
    } catch {}
  };
  eventSource.onerror = () => {};
}

function handleEvent(msg) {
  switch (msg.type) {
    case "stage":
      markStageActive(msg.stage);
      document.getElementById("bar").value = msg.percent || 0;
      document.getElementById("stage-msg").textContent = msg.message || "";
      document.getElementById("eta").textContent = fmtEta(msg.eta_seconds);
      break;
    case "segment": {
      const box = document.getElementById("live-transcript");
      const div = document.createElement("div");
      div.className = "segment";
      const time = document.createElement("span");
      time.className = "segment-time";
      time.textContent = `${fmtTime(msg.start)} – ${fmtTime(msg.end)}`;
      const text = document.createElement("span");
      text.textContent = msg.text;
      div.appendChild(time);
      div.appendChild(text);
      box.appendChild(div);
      box.scrollTop = box.scrollHeight;
      break;
    }
    case "done":
      if (eventSource) { eventSource.close(); eventSource = null; }
      document.getElementById("done-title").textContent = STRINGS.doneTitle;
      const list = document.getElementById("done-files");
      list.replaceChildren();
      (msg.files || []).forEach(f => {
        const li = document.createElement("li");
        li.textContent = f;
        list.appendChild(li);
      });
      const notice = document.getElementById("done-notice");
      notice.textContent = msg.notice || "";
      notice.hidden = !msg.notice;
      const replay = document.getElementById("open-replay");
      if (msg.replay_url) {
        replay.href = msg.replay_url;
        replay.hidden = false;
      } else {
        replay.hidden = true;
      }
      show("done");
      break;
    case "error":
      if (eventSource) { eventSource.close(); eventSource = null; }
      document.getElementById("stopped-msg").textContent = msg.message;
      show("stopped");
      break;
    case "cancelled":
      if (eventSource) { eventSource.close(); eventSource = null; }
      document.getElementById("stopped-msg").textContent = STRINGS.cancelled;
      show("stopped");
      break;
  }
}

function resetToIdle(keepSource) {
  if (eventSource) { eventSource.close(); eventSource = null; }
  document.getElementById("source").value = keepSource ? document.getElementById("source").value : "";
  document.getElementById("folder-name").value = "";
  document.getElementById("model").value = "medium";
  document.getElementById("outputs").replaceChildren();
  document.getElementById("plan-notes").textContent = "";
  document.getElementById("model-row").hidden = true;
  document.getElementById("quality-row").hidden = true;
  document.getElementById("quality").replaceChildren();
  document.getElementById("no-audio-banner").hidden = true;
  document.getElementById("start-btn").disabled = true;
  document.getElementById("bar").value = 0;
  document.getElementById("stage-msg").textContent = "";
  document.getElementById("eta").textContent = "";
  document.getElementById("live-transcript").replaceChildren();
  document.getElementById("stages").replaceChildren();
  currentQualities = [];
  currentKeep = [];
  clearError();
  show("idle");
}

document.getElementById("check-btn").addEventListener("click", () => {
  const source = document.getElementById("source").value.trim();
  if (!source) return;
  show("checking");
  clearError();
  api("/api/check", { source }).then(res => {
    if (!res.ok) {
      setError(res.reason || STRINGS.checkFailed);
      show("idle");
      return;
    }
    clearError();
    currentKind = res.kind;
    currentNoAudio = !!res.no_audio;
    currentQualities = res.qualities || [];
    const qualitySelect = document.getElementById("quality");
    qualitySelect.replaceChildren();
    currentQualities.forEach(q => {
      const opt = document.createElement("option");
      opt.value = q.id;
      opt.textContent = q.label;
      qualitySelect.appendChild(opt);
    });
    buildSummary(res);
    document.getElementById("no-audio-banner").hidden = !res.no_audio;
    renderOutputs(res.outputs || []);
    onOutputChange();
    show("options");
  });
});

document.getElementById("source").addEventListener("keydown", e => {
  if (e.key === "Enter") document.getElementById("check-btn").click();
});

document.getElementById("start-btn").addEventListener("click", () => {
  const source = document.getElementById("source").value.trim();
  const folder_name = document.getElementById("folder-name").value.trim();
  const outputs = Array.from(document.querySelectorAll("#outputs input[type=checkbox]:checked")).map(c => c.value);
  const model = document.getElementById("model").value;
  const qualitySelect = document.getElementById("quality");
  const quality = qualitySelect.options.length > 0 ? qualitySelect.value : "best";
  clearError();
  api("/api/start", { source, folder_name, outputs, model, quality }).then(res => {
    if (!res.ok) {
      setError(res.reason);
      return;
    }
    buildStages(currentPipeline);
    show("running");
    openEventSource();
  });
});

document.getElementById("cancel-btn").addEventListener("click", () => {
  document.getElementById("stage-msg").textContent = STRINGS.cancelling;
  api("/api/cancel", {});
});

document.getElementById("open-folder-btn").addEventListener("click", () => {
  api("/api/open-folder", {});
});

document.getElementById("new-btn").addEventListener("click", () => resetToIdle(false));
document.getElementById("retry-btn").addEventListener("click", () => resetToIdle(true));

api("/api/state").then(res => {
  if (res.state && res.state !== "idle") {
    if (res.plan_pipeline) {
      currentPipeline = res.plan_pipeline;
      buildStages(currentPipeline);
    }
    show("running");
    openEventSource();
  }
});