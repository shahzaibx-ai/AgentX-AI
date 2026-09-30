// End-to-end voice test: real web app + API + LiveKit server + agent (local speech stand-ins).
//
//   npm i -D playwright-core            (or playwright; uses your installed Chromium/Chrome)
//   BASE_URL=http://localhost:3000 node voice_e2e.js desktop|mobile|dark|all
//
// Env: BASE_URL (default http://localhost:3000), OUT (screenshot dir, default ./voice-e2e-out),
//      CHROME_PATH (browser executable; otherwise Playwright's own Chromium, or @sparticuz/chromium).
// Exits 1 when a step times out, nothing is saved, or the page logs errors.
const fs = require("fs");
const path = require("path");

// Resolve packages from the current folder first, so the test can live anywhere.
function load(name) {
  return require(require.resolve(name, { paths: [process.cwd(), __dirname] }));
}
let chromium;
try {
  ({ chromium } = load("playwright-core"));
} catch {
  ({ chromium } = load("playwright"));
}

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const OUT = process.env.OUT || path.join(process.cwd(), "voice-e2e-out");
fs.mkdirSync(OUT, { recursive: true });
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const MEDIA_FLAGS = [
  "--use-fake-ui-for-media-stream",
  "--use-fake-device-for-media-stream",
  "--autoplay-policy=no-user-gesture-required",
];

async function launch() {
  if (process.env.CHROME_PATH) {
    return chromium.launch({ executablePath: process.env.CHROME_PATH, args: MEDIA_FLAGS, headless: true });
  }
  try {
    return await chromium.launch({ args: MEDIA_FLAGS, headless: true });
  } catch (err) {
    let sparticuz;
    try {
      sparticuz = load("@sparticuz/chromium").default;
    } catch {
      throw err;
    }
    return chromium.launch({
      executablePath: await sparticuz.executablePath(),
      args: [...sparticuz.args, ...MEDIA_FLAGS],
      headless: true,
    });
  }
}

async function run({ name, viewport, colorScheme, fullFlow }) {
  const browser = await launch();
  const context = await browser.newContext({ viewport, colorScheme });
  await context.grantPermissions(["microphone"], { origin: new URL(BASE_URL).origin });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push("console: " + m.text());
  });

  try {
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Start voice mode" }).click();
    log(name, "clicked Start voice mode");

    await page.getByText("Spoken", { exact: true }).first().waitFor({ timeout: 30000 });
    log(name, "user transcript is final");
    await page.getByRole("button", { name: "Stop the reply" }).waitFor({ timeout: 30000 });
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${OUT}/${name}-1-speaking.png` });
    log(name, "agent is speaking");

    if (fullFlow) {
      await page.getByRole("button", { name: "Voice settings" }).click();
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${OUT}/${name}-2-settings.png` });
      await page.keyboard.press("Escape"); // closes the menu, must NOT interrupt the reply
      await page.waitForTimeout(300);

      await page.getByRole("button", { name: "Stop the reply" }).click();
      await page.getByText("Listening…", { exact: true }).first().waitFor({ timeout: 15000 });
      log(name, "Stop interrupted the reply; agent listening again");
      await page.screenshot({ path: `${OUT}/${name}-3-after-stop.png` });

      await page.getByRole("button", { name: "Mute microphone" }).click();
      await page.getByText("Microphone off", { exact: true }).waitFor({ timeout: 5000 });
      await page.screenshot({ path: `${OUT}/${name}-4-muted.png` });
      log(name, "muted");

      await page.getByRole("button", { name: "End voice mode" }).click();
      await page.getByRole("button", { name: "Start voice mode" }).waitFor({ timeout: 10000 });
      await page.waitForTimeout(800);
      await page.screenshot({ path: `${OUT}/${name}-5-saved-chat.png` });
      const saved = await page.evaluate(() => localStorage.getItem("assistant.conversations.v1"));
      const convs = JSON.parse(saved || "[]");
      const voiceMsgs = convs.flatMap((c) => c.messages).filter((m) => m.voice);
      log(name, "saved:", JSON.stringify(convs.map((c) => ({
        title: c.title,
        messages: c.messages.map((m) => `${m.role}${m.voice ? "(voice)" : ""}: ${m.content.slice(0, 40)} | ${m.meta?.model ?? "-"}`),
      })), null, 1));
      if (!voiceMsgs.some((m) => m.role === "user") || !voiceMsgs.some((m) => m.role === "assistant")) {
        throw new Error("voice transcripts were not saved into the chat");
      }
    }
  } finally {
    await browser.close();
  }
  if (errors.length) throw new Error("browser errors:\n" + errors.join("\n"));
  log(name, "PASS");
}

const RUNS = {
  desktop: { name: "desktop", viewport: { width: 1280, height: 800 }, colorScheme: "light", fullFlow: true },
  mobile: { name: "mobile", viewport: { width: 390, height: 844 }, colorScheme: "light" },
  dark: { name: "dark", viewport: { width: 1280, height: 800 }, colorScheme: "dark" },
};

(async () => {
  const which = process.argv[2] || "desktop";
  for (const key of which === "all" ? Object.keys(RUNS) : [which]) await run(RUNS[key]);
  log(`screenshots in ${OUT}`);
})().catch((e) => {
  console.error("TEST FAILED:", e.message);
  process.exit(1);
});
