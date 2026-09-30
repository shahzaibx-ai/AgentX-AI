// End-to-end test of "Add photos": real web app + API + the stand-in Ollama
// (fake_ollama_vision.py, which records what each model received).
//
//   npm i -D playwright-core            (or playwright; uses your installed Chromium/Chrome)
//   BASE_URL=http://localhost:3000 OLLAMA_URL=http://localhost:11434 node photos_e2e.js
//
// Env: BASE_URL, OLLAMA_URL (the stand-in; must be the API's OLLAMA_HOST), OUT (screenshots,
//      default ./photos-e2e-out), CHROME_PATH (browser executable; otherwise Playwright's
//      Chromium, or @sparticuz/chromium). The API needs no cloud keys.
// Prints PASS/FAIL per check and exits 1 on any failure or page error.
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
const OLLAMA_URL = process.env.OLLAMA_URL || "http://localhost:11434";
const OUT = process.env.OUT || path.join(process.cwd(), "photos-e2e-out");
const FIX = path.join(__dirname, "fixtures");
const f = (name) => path.join(FIX, name);
fs.mkdirSync(OUT, { recursive: true });

let failures = 0;
const ok = (cond, msg) => {
  console.log(`${cond ? "PASS" : "FAIL"} ${msg}`);
  if (!cond) failures++;
};
const received = () => fetch(`${OLLAMA_URL}/log`).then((r) => r.json());
const lastRequest = async () => (await received()).at(-1);

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

const idbCount = (page) =>
  page.evaluate(
    () =>
      new Promise((resolve) => {
        const req = indexedDB.open("assistant.images");
        req.onsuccess = () => {
          const count = req.result.transaction("images").objectStore("images").count();
          count.onsuccess = () => resolve(count.result);
        };
      }),
  );

async function main() {
  const browser = await launch();
  const errors = [];
  const watch = (page) => {
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));
  };
  await fetch(`${OLLAMA_URL}/log`, { method: "DELETE" });

  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  watch(p);
  await p.goto(BASE_URL);
  // Start clean: no saved chats, photos or model choice.
  await p.evaluate(async () => {
    localStorage.clear();
    await new Promise((r) => {
      const d = indexedDB.deleteDatabase("assistant.images");
      d.onsuccess = d.onerror = d.onblocked = () => r();
    });
  });
  await p.reload();
  await p.waitForTimeout(1500);
  const picker = () => p.locator("header button").nth(1);
  const choose = async (page, name) => {
    await page.locator("header button").nth(1).click();
    await page.getByRole("menuitemradio", { name }).click();
    await page.waitForTimeout(300);
  };

  // ---- adding: resize, HEIC, broken file
  await p.getByRole("button", { name: "Add photos" }).click();
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${OUT}/01-menu.png` });
  await p.keyboard.press("Escape");
  await p.setInputFiles('[data-testid="photo-input"]', [
    f("large-4032x3024.jpg"),
    f("IMG_5520.heic"),
    f("broken.png"),
    f("receipt.jpg"),
  ]);
  await p.waitForTimeout(2000);
  const titles = await p.locator('ul[aria-label="Photos to send"] li[title]').evaluateAll((els) => els.map((e) => e.title));
  const alerts = await p.getByRole("alert").allInnerTexts();
  ok(alerts.some((a) => a.includes("HEIC photos aren't supported")), "HEIC rejected with a how-to");
  ok(alerts.some((a) => a.includes("couldn't be read as an image")), "broken file rejected");
  ok(titles.some((t) => t.includes("2048×1536 (resized from 4032×3024)")), "large photo resized to 2048 px");
  ok(await p.getByText("2 of 5 photos").isVisible(), "photo count shown");
  ok(!(await p.getByRole("button", { name: "Start voice mode" }).count()), "voice button hidden while photos are attached");
  ok(await p.getByText("Auto will answer with").isVisible(), "Auto names the vision model");
  ok(await p.getByText("Photos stay on this computer").isVisible(), "privacy line (local)");
  ok((await picker().innerText()).includes("gemma3:4b"), "picker shows the vision model for Auto");
  await p.screenshot({ path: `${OUT}/02-attached.png` });

  // ---- text-only model: blocked, one-click switch
  await picker().click();
  await p.waitForTimeout(300);
  ok((await p.getByRole("menuitemradio", { name: /gemma3:4b/ }).innerText()).includes("Sees images"), "picker tags vision models");
  await p.screenshot({ path: `${OUT}/03-picker.png` });
  await p.getByRole("menuitemradio", { name: /llama3\.2/ }).click();
  await p.waitForTimeout(300);
  ok(await p.getByText("can't see images. Switch to a model").isVisible(), "text-only warning");
  ok(await p.getByRole("button", { name: "Send message" }).isDisabled(), "send blocked for a text-only model");
  await p.screenshot({ path: `${OUT}/04-text-only.png` });
  await p.getByRole("button", { name: "Use gemma3:4b" }).click();
  await p.waitForTimeout(300);
  ok(!(await p.getByRole("button", { name: "Send message" }).isDisabled()), "switching unblocks send");

  // ---- viewer from the tray
  await p.getByRole("button", { name: "View receipt.jpg" }).click();
  await p.waitForTimeout(400);
  ok(await p.getByRole("dialog").isVisible(), "viewer opens from the tray");
  await p.keyboard.press("Escape");
  await p.waitForTimeout(300);

  // ---- send
  for (const n of ["IMG_5520.heic", "broken.png"]) await p.getByRole("button", { name: `Dismiss ${n}` }).click();
  await p.locator("#composer").fill("What's the total?");
  await p.keyboard.press("Enter");
  await p.waitForTimeout(300);
  ok(await p.getByText(/Looking at 2 photos/).isVisible(), "'Looking at 2 photos…' while waiting");
  await p.waitForTimeout(2500);
  ok(await p.getByText("I can see 2 photo(s)").isVisible(), "reply streamed");
  let last = await lastRequest();
  ok(last.model === "gemma3:4b" && last.messages.at(-1).images.length === 2, "vision model received 2 photos");
  ok(last.messages.at(-1).images.every((i) => i.head.startsWith("ffd8ff")), "photos arrived as JPEG bytes");
  await p.screenshot({ path: `${OUT}/05-sent.png` });

  await p.getByRole("button", { name: "View large-4032x3024.jpg" }).click();
  await p.waitForTimeout(400);
  ok((await p.getByRole("dialog").innerText()).includes("1 of 2"), "gallery viewer counter");
  await p.keyboard.press("ArrowRight");
  await p.waitForTimeout(200);
  ok((await p.getByRole("dialog").innerText()).includes("receipt.jpg"), "arrow keys move between photos");
  await p.screenshot({ path: `${OUT}/06-viewer.png` });
  await p.keyboard.press("Escape");

  // ---- follow-up on a text-only model: earlier photos become a note
  await choose(p, /llama3\.2/);
  ok(await p.getByText("it only gets a note").isVisible(), "notice about earlier photos");
  await p.locator("#composer").fill("Thanks, summarise that.");
  await p.keyboard.press("Enter");
  await p.waitForTimeout(2500);
  last = await lastRequest();
  ok(last.model === "llama3.2:latest" && last.messages.every((m) => !m.images.length), "text-only model got no photos");
  ok(last.messages.some((m) => m.content.startsWith("[Shared 2 photos]")), "photos described as a note");

  // ---- paste (Auto again), Office-style paste, photo-only message
  await choose(p, /^Auto/);
  await p.evaluate(async () => {
    const c = Object.assign(document.createElement("canvas"), { width: 300, height: 200 });
    c.getContext("2d").fillRect(0, 0, 300, 200);
    const png = await new Promise((r) => c.toBlob(r, "image/png"));
    const dt = new DataTransfer();
    dt.items.add(new File([png], "pasted.png", { type: "image/png" }));
    document.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
  });
  await p.waitForTimeout(800);
  ok(await p.getByText("1 of 5 photos").isVisible(), "paste adds a photo");
  await p.evaluate(async () => {
    const c = Object.assign(document.createElement("canvas"), { width: 20, height: 20 });
    const png = await new Promise((r) => c.toBlob(r, "image/png"));
    const dt = new DataTransfer();
    dt.items.add(new File([png], "table.png", { type: "image/png" }));
    dt.setData("text/plain", "A\tB");
    document.querySelector("#composer").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  });
  await p.waitForTimeout(500);
  ok(await p.getByText("1 of 5 photos").isVisible(), "text + picture paste into the input keeps the text only");
  await p.getByRole("button", { name: "Send message" }).click();
  await p.waitForTimeout(2500);
  last = await lastRequest();
  ok(last.model === "gemma3:4b", "a chat with photos uses the vision model on Auto");
  ok(last.messages.at(-1).content === "" && last.messages.at(-1).images[0].head === "89504e47", "photo-only message sent as PNG");
  ok(last.messages.reduce((n, m) => n + m.images.length, 0) === 3, "earlier photos sent again (3 in total)");

  // ---- persistence
  await p.reload();
  await p.waitForTimeout(1500);
  await p.locator("nav[aria-label=Conversations] button").first().click();
  await p.waitForTimeout(800);
  const shown = await p.locator("main img").evaluateAll((els) => els.filter((e) => e.complete && e.naturalWidth > 0).length);
  ok(shown === 3, `photos show after reload (${shown})`);
  ok((await p.locator('nav[aria-label=Conversations] [aria-label="Has photos"]').count()) === 1, "sidebar marks chats with photos");

  // ---- cleanup: only old unreferenced photos are deleted
  await p.setInputFiles('[data-testid="photo-input"]', [f("receipt.jpg")]);
  await p.waitForTimeout(800);
  await p.evaluate(
    () =>
      new Promise((r) => {
        const req = indexedDB.open("assistant.images");
        req.onsuccess = () => {
          const tx = req.result.transaction("images", "readwrite");
          tx.objectStore("images").put({ id: "old-orphan", blob: new Blob(["x"]), createdAt: Date.now() - 2 * 86400000 });
          tx.oncomplete = r;
        };
      }),
  );
  const before = await idbCount(p);
  await p.reload();
  await p.waitForTimeout(1500);
  const after = await idbCount(p);
  ok(after === before - 1, `cleanup removes only old orphans (${before} -> ${after})`);

  // ---- limits and drop overlay
  await p.setInputFiles('[data-testid="photo-input"]', Array(6).fill(f("receipt.jpg")));
  await p.waitForTimeout(1200);
  ok(await p.getByText("5 of 5 photos").isVisible(), "capped at 5 per message");
  ok(await p.getByText("Up to 5 photos per message.").isVisible(), "limit message");
  await p.evaluate(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(["x"], "a.png", { type: "image/png" }));
    window.dispatchEvent(new DragEvent("dragenter", { dataTransfer: dt, bubbles: true, cancelable: true }));
  });
  await p.waitForTimeout(300);
  ok(await p.getByText("Drop photos to add them").isVisible(), "drop overlay");
  await p.screenshot({ path: `${OUT}/07-drop.png` });
  await p.keyboard.press("Escape");

  // ---- dark and phone
  const dark = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" })).newPage();
  watch(dark);
  await dark.goto(BASE_URL);
  await dark.waitForTimeout(1200);
  await dark.setInputFiles('[data-testid="photo-input"]', [f("receipt.jpg"), f("IMG_5520.heic")]);
  await dark.waitForTimeout(800);
  await choose(dark, /llama3\.2/);
  await dark.screenshot({ path: `${OUT}/08-dark-text-only.png` });
  const phone = await (await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })).newPage();
  watch(phone);
  await phone.goto(BASE_URL);
  await phone.waitForTimeout(1200);
  await phone.setInputFiles('[data-testid="photo-input"]', [f("receipt.jpg"), f("large-4032x3024.jpg"), f("IMG_5520.heic")]);
  await phone.waitForTimeout(1500);
  await phone.screenshot({ path: `${OUT}/09-phone.png` });
  ok((await phone.evaluate(() => document.documentElement.scrollWidth)) <= 390, "no sideways scrolling on a phone");

  ok(!errors.length, errors.length ? "page errors:\n  " + errors.join("\n  ") : "no page errors");
  await browser.close();
  console.log(`\n${failures ? `${failures} check(s) failed` : "All photo checks passed"} · screenshots in ${OUT}`);
  process.exit(failures ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
