// record-demo.mjs — regenerate assets/demo.gif + assets/demo-card.png.
//
// The browser-app analogue of the capstone's demo.tape: drives the REAL app
// against the REAL index in a scripted browser session, so every streamed
// token and every path:line citation in the recording is genuine, not staged.
// Refuses to record if the backend is on the mock provider.
//
// Prereqs (from the repo root):
//   docker start askrepo-live-pg
//   cd frontend && npm run build
// Then run THROUGH secrun so keys flow via the environment (nothing secret
// appears in the recording):
//   cd frontend && secrun env AMR_PREFER_LOCAL=0 \
//     DATABASE_URL=postgresql://postgres:pg@localhost:5434/postgres \
//     npm run demo:gif
//
// Outputs:
//   assets/demo.gif       — the animated README demo (960px wide, 12fps)
//   assets/demo-card.png  — a 1280x640 still for the GitHub social preview

import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { chromium } from "playwright";

const PORT = 8199;
const BASE = `http://localhost:${PORT}`;
const QUESTION =
  "How does the local-to-foundation fallback work when streaming a completion?";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const server = spawn(
  "../.venv/bin/uvicorn",
  ["askrepo_live.main:app", "--app-dir", "../backend", "--port", String(PORT)],
  { stdio: "inherit" },
);

function die(msg) {
  console.error(`record-demo: ${msg}`);
  server.kill();
  process.exit(1);
}

let health = null;
for (let i = 0; i < 40 && !health; i++) {
  try {
    health = await (await fetch(`${BASE}/healthz`)).json();
  } catch {
    await sleep(500);
  }
}
if (!health?.ok) die("backend did not come up");
if (health.provider !== "real") {
  die(
    `provider is "${health.provider}" — refusing to record a mock demo. ` +
      "Run through secrun with DATABASE_URL and AMR_PREFER_LOCAL=0 set.",
  );
}

const videoDir = mkdtempSync(path.join(os.tmpdir(), "askrepo-demo-"));
const browser = await chromium.launch({ channel: "chrome" });
const context = await browser.newContext({
  viewport: { width: 1280, height: 640 },
  recordVideo: { dir: videoDir, size: { width: 1280, height: 640 } },
  colorScheme: "dark",
});
const page = await context.newPage();
await page.goto(BASE);
await page.waitForSelector("select option");
await sleep(800);

await page.locator("textarea").pressSequentially(QUESTION, { delay: 40 });
await sleep(500);
await page.getByRole("button", { name: "Ask" }).click();

// follow the streaming answer down the page until the done-frame footer lands
const start = Date.now();
while (Date.now() - start < 90_000) {
  if ((await page.locator(".answer-meta").count()) > 0) break;
  await page.evaluate(() =>
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }),
  );
  await sleep(600);
}
if ((await page.locator(".answer-meta").count()) === 0) {
  die("answer never finished — is the model reachable?");
}

// linger on the sources, then return to the top for the social-preview still
await page.evaluate(() =>
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }),
);
await sleep(2000);
await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
await sleep(1500);
mkdirSync("../assets", { recursive: true });
await page.screenshot({ path: "../assets/demo-card.png" });
await sleep(500);

await context.close(); // flushes the video file
await browser.close();
server.kill();

const webm = readdirSync(videoDir).find((f) => f.endsWith(".webm"));
if (!webm) die("no video was recorded");
execFileSync(
  "ffmpeg",
  [
    "-y",
    "-i",
    path.join(videoDir, webm),
    "-vf",
    "fps=12,scale=960:-1:flags=lanczos," +
      "split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]" +
      "paletteuse=dither=bayer:bayer_scale=5",
    "-loop",
    "0",
    "../assets/demo.gif",
  ],
  { stdio: "inherit" },
);
rmSync(videoDir, { recursive: true, force: true });
console.log("wrote assets/demo.gif and assets/demo-card.png");
