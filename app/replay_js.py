JS = r"""
(function () {
    const segmentsEl = document.getElementById("segments");
    const segments = JSON.parse(segmentsEl.textContent);
    const video = document.getElementById("video");
    const transcript = document.getElementById("transcript");
    const ccToggle = document.getElementById("cc-toggle");
    const speedSelect = document.getElementById("speed");
    const replayLineBtn = document.getElementById("replay-line");
    const settingsToggle = document.getElementById("settings-toggle");
    const settingsPanel = document.getElementById("settings-panel");
    const setFont = document.getElementById("set-font");
    const setColor = document.getElementById("set-color");
    const setSize = document.getElementById("set-size");
    const setBg = document.getElementById("set-bg");
    const setBrightness = document.getElementById("set-brightness");
    const setBold = document.getElementById("set-bold");
    const setItalic = document.getElementById("set-italic");
    const setReset = document.getElementById("set-reset");

    function formatTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        if (h > 0) {
            return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
        }
        return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    }

    const track = video.addTextTrack("captions", "English", "en");
    track.mode = "showing";
    for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (seg.end > seg.start) {
            track.addCue(new VTTCue(seg.start, seg.end, seg.text));
        }
        const line = document.createElement("div");
        line.className = "line";
        line.dataset.i = String(i);
        const ts = document.createElement("span");
        ts.className = "ts";
        ts.textContent = formatTime(seg.start);
        const tx = document.createElement("span");
        tx.className = "tx";
        tx.textContent = seg.text;
        line.appendChild(ts);
        line.appendChild(tx);
        line.addEventListener("click", function () {
            video.currentTime = seg.start;
            video.play().catch(function () {});
        });
        transcript.appendChild(line);
    }

    const lines = transcript.querySelectorAll(".line");
    let activeIndex = -1;
    let captionsOn = true;

    function updateActive(currentTime) {
        let newIndex = -1;
        for (let i = 0; i < segments.length; i++) {
            if (segments[i].start <= currentTime && currentTime < segments[i].end) {
                newIndex = i;
                break;
            }
        }
        if (newIndex !== activeIndex) {
            if (activeIndex >= 0) {
                lines[activeIndex].classList.remove("active");
            }
            if (newIndex >= 0) {
                lines[newIndex].classList.add("active");
                lines[newIndex].scrollIntoView({ block: "nearest" });
            }
            activeIndex = newIndex;
        }
    }

    video.addEventListener("timeupdate", function () {
        updateActive(video.currentTime);
    });

    ccToggle.addEventListener("click", function () {
        captionsOn = !captionsOn;
        ccToggle.setAttribute("aria-pressed", captionsOn ? "true" : "false");
        track.mode = captionsOn ? "showing" : "hidden";
    });

    speedSelect.addEventListener("change", function () {
        video.playbackRate = parseFloat(speedSelect.value);
    });

    replayLineBtn.addEventListener("click", function () {
        let targetIndex = activeIndex;
        if (targetIndex < 0) {
            for (let i = segments.length - 1; i >= 0; i--) {
                if (segments[i].start <= video.currentTime) {
                    targetIndex = i;
                    break;
                }
            }
        }
        if (targetIndex >= 0) {
            video.currentTime = segments[targetIndex].start;
            video.play().catch(function () {});
        }
    });

    const DEFAULTS = {
        font: "system-ui",
        color: "#ffffff",
        size: 20,
        bg: "#101418",
        brightness: 100,
        bold: false,
        italic: false
    };

    function loadSettings() {
        try {
            const raw = localStorage.getItem("subtitled-video.settings");
            if (raw) {
                const parsed = JSON.parse(raw);
                const s = {};
                s.font = typeof parsed.font === "string" ? parsed.font : DEFAULTS.font;
                s.color = typeof parsed.color === "string" ? parsed.color : DEFAULTS.color;
                s.size = typeof parsed.size === "number" ? parsed.size : DEFAULTS.size;
                s.bg = typeof parsed.bg === "string" ? parsed.bg : DEFAULTS.bg;
                s.brightness = typeof parsed.brightness === "number" ? parsed.brightness : DEFAULTS.brightness;
                s.bold = typeof parsed.bold === "boolean" ? parsed.bold : DEFAULTS.bold;
                s.italic = typeof parsed.italic === "boolean" ? parsed.italic : DEFAULTS.italic;
                if (s.size < 12) s.size = 12;
                if (s.size > 48) s.size = 48;
                if (s.brightness < 20) s.brightness = 20;
                if (s.brightness > 200) s.brightness = 200;
                return s;
            }
        } catch (e) {
        }
        return { ...DEFAULTS };
    }

    function saveSettings(s) {
        try {
            localStorage.setItem("subtitled-video.settings", JSON.stringify(s));
        } catch (e) {
        }
    }

    function applySettings(s) {
        const root = document.documentElement;
        root.style.setProperty("--sub-font", s.font);
        root.style.setProperty("--sub-color", s.color);
        root.style.setProperty("--sub-size", s.size + "px");
        root.style.setProperty("--sub-weight", s.bold ? "700" : "400");
        root.style.setProperty("--sub-style", s.italic ? "italic" : "normal");
        root.style.setProperty("--sub-bg", s.bg);
        const hex = s.bg.replace("#", "");
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        const factor = s.brightness / 100;
        const rr = Math.round(Math.min(255, Math.max(0, r * factor)));
        const gg = Math.round(Math.min(255, Math.max(0, g * factor)));
        const bb = Math.round(Math.min(255, Math.max(0, b * factor)));
        root.style.setProperty("--sub-cue-bg", "rgba(" + rr + ", " + gg + ", " + bb + ", 0.9)");
    }

    let settings = loadSettings();

    setFont.value = settings.font;
    setColor.value = settings.color;
    setSize.value = String(settings.size);
    setBg.value = settings.bg;
    setBrightness.value = String(settings.brightness);
    setBold.checked = settings.bold;
    setItalic.checked = settings.italic;

    applySettings(settings);

    function updateAndSave() {
        settings.font = setFont.value;
        settings.color = setColor.value;
        settings.size = parseInt(setSize.value, 10);
        settings.bg = setBg.value;
        settings.brightness = parseInt(setBrightness.value, 10);
        settings.bold = setBold.checked;
        settings.italic = setItalic.checked;
        if (settings.size < 12) settings.size = 12;
        if (settings.size > 48) settings.size = 48;
        if (settings.brightness < 20) settings.brightness = 20;
        if (settings.brightness > 200) settings.brightness = 200;
        saveSettings(settings);
        applySettings(settings);
    }

    setFont.addEventListener("change", updateAndSave);
    setColor.addEventListener("input", updateAndSave);
    setSize.addEventListener("input", updateAndSave);
    setBg.addEventListener("input", updateAndSave);
    setBrightness.addEventListener("input", updateAndSave);
    setBold.addEventListener("change", updateAndSave);
    setItalic.addEventListener("change", updateAndSave);

    settingsToggle.addEventListener("click", function () {
        settingsPanel.hidden = !settingsPanel.hidden;
    });

    setReset.addEventListener("click", function () {
        settings = { ...DEFAULTS };
        setFont.value = settings.font;
        setColor.value = settings.color;
        setSize.value = String(settings.size);
        setBg.value = settings.bg;
        setBrightness.value = String(settings.brightness);
        setBold.checked = settings.bold;
        setItalic.checked = settings.italic;
        saveSettings(settings);
        applySettings(settings);
    });
})();
"""