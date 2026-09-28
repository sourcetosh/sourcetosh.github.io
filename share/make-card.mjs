// Renders share/card.jpg, the image a link to the site shows when shared (og:image), from the
// landing page itself: the tilak, the name and the tagline between the boughs and the hills,
// larger than on the page and without the menu, the icons or the drifting petals.
// Needs Microsoft Edge and Node 22 or later. Run from anywhere: node share/make-card.mjs
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const W = 1200, H = 630, QUALITY = 90;
const CARD_CSS = `
  .areas, .socials, .sound, .drift { display: none !important; }
  .stage { padding: 0 !important; }
  :root { --name: 64px !important; --dot: 15px !important; --desc: 21px !important; }
  .bough--l { transform: scale(.86); transform-origin: 100% 50%; } /* kept clear of the card's edges */
  .bough--r { transform: scale(.86); transform-origin: 0 50%; }
`;
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PAGE = new URL("../index.html?freeze=9000", import.meta.url).href; // ?freeze: every intro animation at its end, no gate
const OUT = fileURLToPath(new URL("card.jpg", import.meta.url));
const PORT = 9341;

const profile = mkdtempSync(join(tmpdir(), "card-edge-"));
const edge = spawn(EDGE, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "--no-first-run",
  "--no-default-browser-check", "--disable-extensions", "--mute-audio", "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"],
  { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let target = null;
for (let i = 0; i < 80 && !target; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === "page"); } catch { /* starting */ }
  if (!target) await sleep(250);
}
if (!target) throw new Error("Edge did not start");
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let seq = 0;
const waits = new Map(), handlers = new Set();
ws.addEventListener("message", (m) => {
  const d = JSON.parse(m.data);
  if (d.id && waits.has(d.id)) { waits.get(d.id)(d.result || d.error); waits.delete(d.id); }
  else if (d.method) handlers.forEach((h) => h(d));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++seq; waits.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const loaded = new Promise((r) => handlers.add((d) => d.method === "Page.loadEventFired" && r()));

await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
// The card's styles go in before the intro plants the boughs, so they grow beside the larger name.
await send("Page.addScriptToEvaluateOnNewDocument", { source: `document.addEventListener("DOMContentLoaded", () => {
  const s = document.createElement("style"); s.textContent = ${JSON.stringify(CARD_CSS)}; document.head.append(s); });` });
await send("Page.navigate", { url: PAGE });
await loaded;
await send("Runtime.evaluate", { expression: "document.fonts.ready.then(() => 1)", awaitPromise: true });
await sleep(2500); // the boughs are planted a frame after the fonts, then held
const shot = await send("Page.captureScreenshot", { format: "jpeg", quality: QUALITY, captureBeyondViewport: false });
writeFileSync(OUT, Buffer.from(shot.data, "base64"));
console.log(`${OUT}: ${W}x${H}, ${(Buffer.byteLength(shot.data, "base64") / 1024).toFixed(0)} KB`);

ws.close();
edge.kill();
await sleep(500);
try { rmSync(profile, { recursive: true, force: true }); } catch { /* Edge may still hold it for a moment */ }
process.exit(0);
