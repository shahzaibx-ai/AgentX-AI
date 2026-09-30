// Browser test for a running Sentiment Studio (web + API). Adapts to the enabled models.
//
//   npm i -D playwright-core && npx playwright install chromium   (or set CHROME_PATH)
//   BASE_URL=http://localhost:3000 node studio_e2e.js
//
// Env: BASE_URL (default http://localhost:3000), OUT (screenshots, default ./studio-e2e-out),
//      CHROME_PATH (browser executable). Exits 1 on any failed check or browser error.
const fs = require("fs");
const path = require("path");

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
const OUT = process.env.OUT || path.join(process.cwd(), "studio-e2e-out");
fs.mkdirSync(OUT, { recursive: true });
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const check = (cond, msg) => {
  if (!cond) throw new Error("CHECK FAILED: " + msg);
  log("✓", msg);
};

async function launch() {
  if (process.env.CHROME_PATH) return chromium.launch({ executablePath: process.env.CHROME_PATH });
  try {
    return await chromium.launch();
  } catch (err) {
    let sparticuz;
    try {
      sparticuz = load("@sparticuz/chromium").default;
    } catch {
      throw err;
    }
    return chromium.launch({ executablePath: await sparticuz.executablePath(), args: sparticuz.args });
  }
}

const bars = (p) =>
  p.getByRole("tabpanel", { name: "Analyze" }).locator("ul[aria-label='Class probabilities'] li");

(async () => {
  const browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push("pageerror " + e.message));
  p.on("console", (m) => m.type() === "error" && errors.push("console " + m.text()));

  const catalog = await (await p.request.get(`${BASE_URL}/api/models`)).json();
  const models = catalog.models;
  const byDefault = models.find((m) => m.default);
  log(`models: ${models.map((m) => m.name).join(", ")} (default ${byDefault.name})`);

  await p.goto(BASE_URL, { waitUntil: "networkidle" });
  await p.waitForFunction(
    (name) => document.querySelector("[aria-label='Model']")?.innerText.includes(name),
    byDefault.name,
    { timeout: 20000 },
  );
  check(true, `default model ${byDefault.name} selected`);

  // Example → analysis
  await p.locator("[aria-label='Examples'] button").first().click();
  await p.waitForFunction(() => document.querySelectorAll("ul[aria-label='Class probabilities'] li").length > 0, null, {
    timeout: 600000,
  });
  check((await bars(p).count()) === byDefault.labels.length, `${byDefault.labels.length} probability bars`);
  check(await p.getByText("Integrated gradients", { exact: true }).isVisible(), "word influence shown");
  await p.screenshot({ path: `${OUT}/1-analyze.png` });

  // Own text with Ctrl+Enter → history
  await p.locator("#analyze-text").fill("The support team was rude and the refund never arrived.");
  await p.locator("#analyze-text").press("Control+Enter");
  await p.waitForFunction(() => document.querySelectorAll("nav[aria-label='Recent analyses'] button").length >= 2);
  check(true, "Ctrl+Enter analyzes and saves to history");

  // Every other model: switching re-runs the text with that model's classes
  for (const m of models.filter((x) => !x.default)) {
    await p.getByRole("combobox", { name: "Model" }).click();
    await p.getByRole("option", { name: new RegExp(m.name) }).click();
    // The result header names the model that produced it (its id is the chip's title).
    await p.waitForFunction(
      ([id, n]) =>
        !!document.querySelector(`[title="${id}"]`) &&
        document.querySelectorAll("[role=tabpanel] ul[aria-label='Class probabilities'] li").length === n,
      [m.id, m.labels.length],
      { timeout: 600000 },
    );
    check(true, `${m.name}: re-ran with ${m.labels.length} classes`);
  }

  // Batch + CSV export
  await p.getByRole("tab", { name: "Batch" }).click();
  await p.getByRole("button", { name: "Use sample" }).click();
  await p.getByRole("button", { name: "Run batch" }).click();
  await p.getByText("Label distribution", { exact: false }).first().waitFor({ timeout: 600000 });
  const rows = await p.getByRole("tabpanel", { name: "Batch" }).locator("table tbody tr").count();
  check(rows === 8, "batch table has 8 rows");
  const [download] = await Promise.all([
    p.waitForEvent("download"),
    p.getByRole("button", { name: "Download CSV" }).click(),
  ]);
  const csv = fs.readFileSync(await download.path(), "utf8").replace(/^﻿/, "").split("\r\n");
  check(csv.length === 9 && csv[0].startsWith("text,label,confidence,p_"), "CSV export: header + 8 rows");
  await p.screenshot({ path: `${OUT}/2-batch.png` });

  // Model view
  await p.getByRole("tab", { name: "Model" }).click();
  await p.getByText("Model card").waitFor();
  check((await p.getByRole("tabpanel", { name: "Model" }).locator("tbody tr").count()) >= models.length, "model table lists every model");
  await p.screenshot({ path: `${OUT}/3-model.png` });

  // Dark mode
  await p.getByRole("tab", { name: "Analyze" }).click();
  await p.getByRole("button", { name: "Switch between light and dark" }).click();
  check(await p.evaluate(() => document.documentElement.classList.contains("dark")), "dark mode");
  await p.waitForTimeout(500);
  await p.screenshot({ path: `${OUT}/4-dark.png` });

  // Phone width: no sideways scrolling
  const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await phone.goto(BASE_URL, { waitUntil: "networkidle" });
  const width = await phone.evaluate(() => document.documentElement.scrollWidth);
  check(width <= 390, `phone layout fits (${width}px)`);
  await phone.screenshot({ path: `${OUT}/5-phone.png` });

  await browser.close();
  if (errors.length) throw new Error("browser errors:\n" + errors.join("\n"));
  log(`PASS · screenshots in ${OUT}`);
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
