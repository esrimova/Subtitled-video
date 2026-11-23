// Drives a generated replay page (opened as file://) in headless Chrome over the DevTools protocol (Node 22+).
// usage: node replay_e2e.js <replay-index.html path> <chrome.exe> <profile-dir>
const { spawn } = require("child_process");
const { pathToFileURL } = require("url");
const [PAGE, CHROME, PROFILE] = process.argv.slice(2);
const PORT = 9344;
let fails = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, cond, extra) {
  console.log((cond ? "PASS  " : "FAIL  ") + name + (cond ? "" : "   -> " + JSON.stringify(extra)));
  if (!cond) fails++;
}

(async () => {
  const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + PROFILE, "--window-size=1200,800", "about:blank"], { stdio: "ignore" });
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
  const ev = async (expr, gesture) => {
    const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true, userGesture: !!gesture });
    if (r.result.exceptionDetails) throw new Error("JS error in: " + expr + " :: " + JSON.stringify(r.result.exceptionDetails.exception));
    return r.result.result.value;
  };
  const click = async (sel) => {
    const p = await ev("(()=>{const r=document.querySelector('" + sel + "').getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()");
    for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x: p.x, y: p.y, button: "left", clickCount: 1 });
  };
  const load = async () => { await send("Page.navigate", { url: pathToFileURL(PAGE).href }); await sleep(800); };

  try {
    await send("Page.enable");
    await load();

    // layout: percentages of the grid container
    for (const w of [1200, 700]) {
      await send("Emulation.setDeviceMetricsOverride", { width: w, height: 800, deviceScaleFactor: 1, mobile: false });
      await sleep(200);
      const r = await ev("(()=>{const p=document.getElementById('player').getBoundingClientRect(),s=document.getElementById('stage').getBoundingClientRect(),d=document.getElementById('side').getBoundingClientRect();return {l:s.width/p.width,r:d.width/p.width,gap:(d.left-s.right)/p.width,scroll:document.documentElement.scrollWidth>innerWidth}})()");
      check("layout 68/4/28 at width " + w, Math.abs(r.l - 0.68) < 0.01 && Math.abs(r.r - 0.28) < 0.01 && Math.abs(r.gap - 0.04) < 0.01, r);
      check("no horizontal scrollbar at width " + w, !r.scroll, r);
    }
    await send("Emulation.clearDeviceMetricsOverride");

    // long subtitle line stays inside the right column
    await ev("document.getElementById('video').currentTime = 1; 1");
    await sleep(600);
    const fit = await ev("(()=>{const c=document.getElementById('current-caption').getBoundingClientRect(),d=document.getElementById('side').getBoundingClientRect();return c.right<=d.right+1&&c.left>=d.left-1})()");
    check("long caption stays inside subtitle column", fit);

    // settings persist after reload, from file://
    await ev("document.getElementById('settings-toggle').click(); 1");
    await ev("(()=>{const b=document.getElementById('set-bold');b.checked=true;b.dispatchEvent(new Event('change'));const s=document.getElementById('set-size');s.value='30';s.dispatchEvent(new Event('input'));return 1})()");
    await load();
    const after = await ev("(()=>{const e=document.getElementById('side').style;return {w:e.getPropertyValue('--sub-weight'),sz:e.getPropertyValue('--sub-size')}})()");
    check("bold + size survive reload", after.w === "700" && after.sz === "30px", after);

    // corrupt storage falls back to defaults without crashing
    await ev("localStorage.setItem('subtitled-video.settings','{not json'); 1");
    await load();
    const def = await ev("document.getElementById('side').style.getPropertyValue('--sub-size')");
    check("corrupt settings fall back to defaults", def === "20px", def);

    // Fullscreen: Chrome refuses real fullscreen to automated sessions ("not granted"), so we check that a real
    // click asks the whole #player (video + subtitle panel) to go fullscreen, not just the <video>.
    await ev("window.__fs=[];for(const id of ['player','video']){const el=document.getElementById(id);el.requestFullscreen=function(){window.__fs.push(id);return Promise.resolve()}};1");
    await click("#fs-toggle");
    await sleep(300);
    check("fullscreen button targets #player, not the video", JSON.stringify(await ev("window.__fs")) === '["player"]', await ev("window.__fs"));
    check("native video fullscreen button is disabled", await ev("document.getElementById('video').controlsList.contains('nofullscreen')"));
    check("CC off/on works", await (async () => {
      await ev("document.getElementById('video').currentTime = 1; 1"); await sleep(600);
      await ev("document.getElementById('cc-toggle').click(); 1");
      const off = await ev("document.getElementById('current-caption').textContent===''");
      await ev("document.getElementById('cc-toggle').click(); 1");
      return off && await ev("document.getElementById('current-caption').textContent.length>0");
    })());
  } catch (e) {
    console.log("FAIL  script error: " + e.message); fails++;
  }
  try { ws.close(); } catch {}
  chrome.kill();
  console.log(fails ? "\n" + fails + " FAILED" : "\nALL PASSED");
  process.exit(fails ? 1 : 0);
})();
