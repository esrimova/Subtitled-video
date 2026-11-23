// Drives the real page in headless Chrome over the DevTools protocol (Node 22+, no packages).
// usage: node ui_e2e.js <app-url-with-token> <short-clip> <long-clip> <chrome.exe> <profile-dir>
const { spawn } = require("child_process");
const [APP, CLIP, LONG, CHROME, PROFILE] = process.argv.slice(2);
const PORT = 9333;
let fails = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, cond, extra) {
  console.log((cond ? "PASS  " : "FAIL  ") + name + (cond ? "" : "   -> " + JSON.stringify(extra)));
  if (!cond) fails++;
}

(async () => {
  const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + PROFILE, "--window-size=1100,900", "about:blank"], { stdio: "ignore" });
  let list;
  for (let i = 0; i < 50; i++) {
    try { list = await (await fetch("http://127.0.0.1:" + PORT + "/json/list")).json(); if (list.length) break; } catch {}
    await sleep(200);
  }
  const page = list.find((t) => t.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const waiting = new Map();
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && waiting.has(d.id)) { waiting.get(d.id)(d); waiting.delete(d.id); } };
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; waiting.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result.exceptionDetails) throw new Error("JS error in: " + expr + " :: " + JSON.stringify(r.result.exceptionDetails.exception));
    return r.result.result.value;
  };
  const until = async (expr, ms = 30000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await ev(expr)) return true; } catch {} await sleep(250); } return false; };
  const errors = [];
  await send("Runtime.enable"); await send("Page.enable");
  ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); if (d.method === "Runtime.exceptionThrown") errors.push(d.params.exceptionDetails.text + " " + JSON.stringify(d.params.exceptionDetails.exception?.description || "")); });

  try {
    // ---- 1. load, check a local clip
    await send("Page.navigate", { url: APP });
    // wait for the scripts too: the button exists in the DOM before app_ui.js has run
    check("page loads with only the source box visible", await until("document.readyState === 'complete' && typeof show === 'function' && document.getElementById('options').hidden && document.getElementById('running').hidden"));
    await ev(`document.getElementById('source').value = ${JSON.stringify(CLIP)}; document.getElementById('check-btn').click(); 1`);
    const optionsShown = await until("!document.getElementById('options').hidden");
    check("options screen appears after the check", optionsShown,
      optionsShown ? "" : await ev("JSON.stringify({hidden: ['idle-section','checking','options','running','done','stopped'].map(i => i + '=' + (document.getElementById(i) ? document.getElementById(i).hidden : 'MISSING')), error: document.getElementById('error').textContent, summary: document.getElementById('summary').textContent, outputs: document.getElementById('outputs').childElementCount, checkDisabled: document.getElementById('check-btn').disabled})"));
    check("'Checking video…' is hidden again", await ev("document.getElementById('checking').hidden"));
    check("summary shows the title", (await ev("document.getElementById('summary').textContent")).length > 3);
    check("four outputs offered", (await ev("document.querySelectorAll('#outputs input[type=checkbox]').length")) === 4);
    check("quality row hidden for a local file", await ev("document.getElementById('quality-row').hidden"));

    // ---- 2. quality row logic (simulated qualities, since the clip is a local file)
    await ev("currentQualities = [{id:'best',label:'Best available (1080p)'},{id:'720',label:'720p'}]; updateModelRow(['download'], ['video']); 1");
    check("quality row shows when video is kept and several qualities exist", !(await ev("document.getElementById('quality-row').hidden")));
    await ev("updateModelRow(['download','audio'], ['audio']); 1");
    check("quality row hides when no video is kept", await ev("document.getElementById('quality-row').hidden"));
    await ev("currentQualities = [{id:'best',label:'Best available (720p)'}]; updateModelRow(['download'], ['video']); 1");
    check("single quality: select disabled and note shown", (await ev("document.getElementById('quality').disabled")) && (await ev("document.getElementById('quality-note').textContent")).length > 0);
    await ev("currentQualities = []; updateModelRow([], []); 1");

    // ---- 3. choose transcript + replay, see the dependency note
    await ev("document.querySelector('#outputs input[value=video]').click(); document.querySelector('#outputs input[value=transcript]').click(); document.querySelector('#outputs input[value=replay]').click(); 1");
    await until("document.getElementById('plan-notes').textContent.length > 0");
    const notes = await ev("document.getElementById('plan-notes').textContent");
    check("plan note explains video.mp4 is kept for the replay", /video\.mp4/.test(notes), notes);
    check("model row visible when transcribing", !(await ev("document.getElementById('model-row').hidden")));
    await ev("document.getElementById('model').value = 'small'; document.getElementById('folder-name').value = 'ui e2e'; document.getElementById('start-btn').click(); 1");
    check("running screen appears", await until("!document.getElementById('running').hidden"));
    check("stage list has 3 rows (audio, transcribe, captions)", (await ev("document.querySelectorAll('#stages li').length")) === 3);
    check("job finishes: done screen", await until("!document.getElementById('done').hidden", 180000));
    check("done lists the four files", (await ev("document.querySelectorAll('#done-files li').length")) === 4);
    check("open-replay link is visible", !(await ev("document.getElementById('open-replay').hidden")));
    const replayHref = await ev("document.getElementById('open-replay').href");

    // ---- 4. the replay page itself
    await send("Page.navigate", { url: replayHref });
    check("replay transcript rows render", await until("document.querySelectorAll('#transcript .line').length > 0"));
    const segs = await ev("JSON.parse(document.getElementById('segments').textContent)");
    check("rows equal embedded segments", (await ev("document.querySelectorAll('#transcript .line').length")) === segs.length);
    await until("document.getElementById('video').readyState >= 1", 15000);
    await ev("document.querySelector('#transcript .line').click(); 1");
    await sleep(600);
    const t = await ev("document.getElementById('video').currentTime");
    check("clicking a line seeks the video to its start", Math.abs(t - segs[0].start) < 0.6, { t, start: segs[0].start });
    await ev(`(() => { const v = document.getElementById('video'); v.currentTime = ${segs[0].start + 0.05}; v.dispatchEvent(new Event('timeupdate')); })()`);
    await sleep(300);
    check("caption overlay shows the current line", (await ev("document.getElementById('caption-overlay').textContent")).trim() === segs[0].text.trim(), await ev("document.getElementById('caption-overlay').textContent"));
    check("current line is highlighted", await ev("document.querySelector('#transcript .line.active') !== null"));
    await ev("document.getElementById('cc-toggle').click(); 1");
    check("CC off hides the overlay", (await ev("document.getElementById('cc-toggle').getAttribute('aria-pressed')")) === "false" && (await ev("getComputedStyle(document.getElementById('caption-overlay')).display")) === "none");
    await ev("document.getElementById('cc-toggle').click(); 1");
    check("CC on shows it again", (await ev("getComputedStyle(document.getElementById('caption-overlay')).display")) !== "none");
    await ev("document.getElementById('speed').value = '0.5'; document.getElementById('speed').dispatchEvent(new Event('change')); 1");
    check("speed selector sets playbackRate", Math.abs((await ev("document.getElementById('video').playbackRate")) - 0.5) < 0.01);

    // ---- 5. cancel from the UI
    await send("Page.navigate", { url: APP });
    await sleep(800);
    await until("document.readyState === 'complete' && typeof show === 'function' && !document.getElementById('check-btn').disabled");
    await ev(`document.getElementById('source').value = ${JSON.stringify(LONG)}; document.getElementById('check-btn').click(); 1`);
    await until("!document.getElementById('options').hidden && document.querySelectorAll('#outputs input[type=checkbox]').length === 4");
    await ev("document.querySelector('#outputs input[value=transcript]').click(); 1");
    await until("!document.getElementById('start-btn').disabled");
    await ev("document.getElementById('model').value = 'small'; document.getElementById('folder-name').value = 'ui cancel'; document.getElementById('start-btn').click(); 1");
    await until("!document.getElementById('running').hidden");
    await until("document.getElementById('stage-msg').textContent.length > 0", 60000);
    await sleep(1500);
    await ev("document.getElementById('cancel-btn').click(); 1");
    check("cancel: stopped screen shows 'Cancelled'", (await until("!document.getElementById('stopped').hidden", 30000)) && /cancel/i.test(await ev("document.getElementById('stopped-msg').textContent")));
    // tab reload mid-state reconstructs the screen
    await send("Page.navigate", { url: APP });
    check("reload after cancel shows the stopped screen (state restored)", await until("!document.getElementById('stopped').hidden", 15000));
    await ev("document.getElementById('retry-btn').click(); 1");
    check("Try again returns to the idle screen", await until("!document.getElementById('check-btn').disabled && document.getElementById('stopped').hidden"));
  } catch (e) {
    check("script ran without an exception", false, String(e.message).slice(0, 300));
  }
  check("no uncaught JS errors in the page", errors.length === 0, errors.slice(0, 3));
  console.log(fails ? "\n" + fails + " FAILED" : "\nALL PASSED");
  ws.close(); chrome.kill(); process.exit(fails ? 1 : 0);
})();
