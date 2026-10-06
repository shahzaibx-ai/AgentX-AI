const { chromium } = require("playwright-core");
// Chromium: PLAYWRIGHT_CHROMIUM (path) or @sparticuz/chromium if installed.
const sparticuz = (() => { try { return require("@sparticuz/chromium").default; } catch { return null; } })();
// Usage: start fake_ollama_vision.py (port 11434), the API with RAG_ENGINE=offline and an
// empty LIBRARY_DATA_DIR, and the web app; then
//   PROJECT=/path/to/project OUT=/tmp/shots node files_e2e.js
const fs = require("fs");
const OUT = process.env.OUT ?? "./files-shots";
fs.mkdirSync(OUT, { recursive: true });
const FIX = `${process.env.PROJECT ?? "."}/api/tests/fixtures/library`;
const URL = process.env.BASE_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch(
    process.env.PLAYWRIGHT_CHROMIUM || !sparticuz
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM }
      : { executablePath: await sparticuz.executablePath(), args: sparticuz.args },
  );
  const errors = [];
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));

  // ---------- Library: create collection, upload docs
  await p.goto(`${URL}/library`); await p.waitForTimeout(1500);
  ok(await p.getByRole("heading", { name: "Overview" }).isVisible(), "library overview loads (open owner mode)");
  await p.screenshot({ path: `${OUT}/01-overview-empty.png` });
  await p.getByRole("link", { name: "Collections" }).click(); await p.waitForTimeout(800);
  await p.getByRole("button", { name: "New collection" }).click();
  await p.getByPlaceholder("HR Policies").fill("HR Policies");
  await p.getByRole("button", { name: "Create" }).click(); await p.waitForTimeout(800);
  await p.getByRole("button", { name: "New collection" }).click();
  await p.getByPlaceholder("HR Policies").fill("Product");
  await p.getByRole("button", { name: "Create" }).click(); await p.waitForTimeout(800);
  ok(await p.getByRole("heading", { name: "Product" }).isVisible(), "collections created");
  await p.screenshot({ path: `${OUT}/02-collections.png` });

  await p.getByRole("link", { name: "Documents" }).first().click(); await p.waitForTimeout(800);
  await p.getByRole("button", { name: "Upload" }).click(); await p.waitForTimeout(300);

  const dlg = p.getByRole("dialog");
  await dlg.locator("select").selectOption({ label: "HR Policies" });
  await p.setInputFiles('[data-testid="library-upload-input"]', [`${FIX}/Employee-Handbook-2026.pdf`, `${FIX}/Travel-Expense-Policy.docx`]);
  await p.screenshot({ path: `${OUT}/03-upload.png` });
  await dlg.getByRole("button", { name: /^Upload/ }).click(); await p.waitForTimeout(1500);
  await p.getByRole("button", { name: "Upload" }).click(); await p.waitForTimeout(300);
  await dlg.locator("select").selectOption({ label: "Product" });
  await p.setInputFiles('[data-testid="library-upload-input"]', [`${FIX}/Product-FAQ.md`]);
  await dlg.getByRole("button", { name: /^Upload/ }).click(); await p.waitForTimeout(4000);
  const rows = await p.locator("tbody tr").count();
  ok(rows === 3, `3 documents listed (${rows})`);
  ok((await p.locator("tbody").innerText()).split("Ready").length - 1 === 3, "all indexed (Ready)");
  // duplicate upload -> replace offer
  await p.getByRole("button", { name: "Upload" }).click(); await p.waitForTimeout(300);
  await dlg.locator("select").selectOption({ label: "Product" });
  await p.setInputFiles('[data-testid="library-upload-input"]', [`${FIX}/Product-FAQ.md`]);
  await dlg.getByRole("button", { name: /^Upload/ }).click(); await p.waitForTimeout(1500);
  ok(await dlg.getByRole("button", { name: /Replace/ }).isVisible(), "duplicate offers Replace");
  await p.screenshot({ path: `${OUT}/04-duplicate.png` });
  await p.keyboard.press("Escape"); await p.waitForTimeout(300);
  // drawer
  await p.getByRole("button", { name: "Employee-Handbook-2026.pdf" }).click(); await p.waitForTimeout(600);
  ok(await p.getByRole("dialog").getByText("Cited in answers").isVisible(), "document drawer opens");
  await p.screenshot({ path: `${OUT}/05-drawer.png` });
  await p.keyboard.press("Escape"); await p.waitForTimeout(300);
  await p.screenshot({ path: `${OUT}/06-documents.png` });

  // retrieval test
  await p.getByRole("link", { name: "Retrieval test" }).click(); await p.waitForTimeout(600);
  await p.getByPlaceholder(/vacation days/).fill("How many requests per minute can an API key make?");
  await p.getByRole("button", { name: "Run test" }).click(); await p.waitForTimeout(2500);
  ok(await p.getByText("Answered from documents").isVisible(), "retrieval test grounded");
  await p.screenshot({ path: `${OUT}/07-test.png` });
  for (const page of ["Overview", "Storage", "Index settings"]) {
    await p.getByRole("link", { name: page }).click(); await p.waitForTimeout(900);
    await p.screenshot({ path: `${OUT}/08-${page.replace(" ", "-")}.png` });
  }
  ok(await p.getByText("RAG_CHUNK_TOKENS").isVisible(), "settings page shows env names");

  // ---------- Chat: Search Library
  await p.goto(URL); await p.waitForTimeout(1500);
  // Voice mode (if installed and configured) must survive the Library install.
  const voice = await p.request.get(`${API}/api/voice/config`).then((r) => (r.ok() ? r.json() : null)).catch(() => null);
  if (voice?.enabled) ok(await p.getByRole("button", { name: "Start voice mode" }).isVisible(), "voice button still shown on an empty composer");
  ok(await p.getByRole("link", { name: /Library/ }).isVisible(), "sidebar Library link");
  await p.getByRole("button", { name: "Add photos and files" }).click(); await p.waitForTimeout(300);
  await p.screenshot({ path: `${OUT}/10-menu.png` });
  await p.getByRole("menuitem", { name: /Search Library/ }).hover(); await p.waitForTimeout(400);
  await p.getByRole("menuitemcheckbox", { name: /Product/ }).click(); await p.waitForTimeout(200);
  await p.screenshot({ path: `${OUT}/11-submenu.png` });
  await p.keyboard.press("Escape"); await p.keyboard.press("Escape"); await p.waitForTimeout(300);
  ok(await p.getByText("Searching Product").isVisible(), "Library pill in composer");
  ok(await p.getByText(/offline test search/).isVisible(), "privacy line for library");
  await p.locator("#composer").fill("How many requests per minute can each API key make?");
  await p.keyboard.press("Enter"); await p.waitForTimeout(3000);
  const answer = await p.locator('[role="log"]').innerText();
  ok(/600/.test(answer), "answer from the library mentions 600");
  ok(await p.getByRole("button", { name: "Source 1" }).first().isVisible(), "citation chip rendered");
  ok(await p.getByText("Sources").isVisible(), "sources list");
  await p.screenshot({ path: `${OUT}/12-answer.png` });
  await p.getByRole("button", { name: "Source 1" }).first().click(); await p.waitForTimeout(600);
  ok(await p.getByRole("link", { name: "Open original" }).isVisible(), "source panel with original link");
  await p.screenshot({ path: `${OUT}/13-source-panel.png` });
  const href = await p.getByRole("link", { name: "Open original" }).getAttribute("href");
  const res = await p.request.get(URL + href);
  ok(res.status() === 200 && /text\/(plain|markdown)|attachment/.test(JSON.stringify(res.headers())), `original served via proxy (${res.status()})`);
  await p.keyboard.press("Escape");

  // ---------- Chat: Add files in a new chat
  await p.getByRole("button", { name: "New chat" }).first().click(); await p.waitForTimeout(800);
  await p.setInputFiles('[data-testid="file-input"]', [`${FIX}/Travel-Expense-Policy.docx`]);
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${OUT}/14-file-uploading.png` });
  await p.waitForTimeout(2500);
  ok(await p.getByText(/Ready/).first().isVisible(), "chat file becomes ready");
  ok(!(await p.getByRole("button", { name: "Start voice mode" }).count()), "voice hidden with files");
  await p.screenshot({ path: `${OUT}/15-file-ready.png` });
  await p.locator("#composer").fill("What is the hotel limit per night?");
  await p.keyboard.press("Enter"); await p.waitForTimeout(3000);
  await p.screenshot({ path: `${OUT}/16-file-answer.png` });
  const t2 = await p.locator('[role="log"]').innerText();
  console.log("file answer:", t2.slice(0, 400).replace(/\n/g, " | "));
  ok(t2.includes("Travel-Expense-Policy.docx"), "file chip on user message");
  // follow-up still uses the file
  await p.locator("#composer").fill("And what about meals?");
  await p.keyboard.press("Enter"); await p.waitForTimeout(3000);
  const msgs = await p.request.get(`${API}/api/library/overview`).then((r) => r.json());
  ok(msgs.totals.chat_files === 1, `1 chat file stored (${msgs.totals.chat_files})`);
  // rejected types
  await p.setInputFiles('[data-testid="file-input"]', { name: "x.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ") });
  await p.waitForTimeout(300);
  ok(await p.getByText(/can't be read/).isVisible(), "unsupported type rejected in tray");
  await p.screenshot({ path: `${OUT}/17-rejected.png` });
  await p.getByRole("button", { name: "Remove x.exe" }).click();

  // delete chat -> file removed after toast closes
  const sidebarItem = p.locator("nav[aria-label=Conversations] li").first();
  await sidebarItem.hover();
  await sidebarItem.getByRole("button", { name: /Options for/ }).click();
  await p.getByRole("menuitem", { name: /Delete/ }).click(); await p.waitForTimeout(6000);
  const after = await p.request.get(`${API}/api/library/overview`).then((r) => r.json());
  ok(after.totals.chat_files === 0, `chat file deleted with chat (${after.totals.chat_files})`);

  // ---------- dark + phone
  await p.emulateMedia({ colorScheme: "dark" });
  await p.goto(`${URL}/library/documents`); await p.waitForTimeout(1200);
  await p.screenshot({ path: `${OUT}/20-docs-dark.png` });
  const ph = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const m = await ph.newPage();
  m.on("pageerror", (e) => errors.push("mobile: " + e.message));
  await m.goto(`${URL}/library`); await m.waitForTimeout(1500);
  await m.screenshot({ path: `${OUT}/21-phone-overview.png`, fullPage: true });
  const sw = await m.evaluate(() => document.documentElement.scrollWidth);
  ok(sw <= 390, `no horizontal scroll on phone overview (${sw})`);
  await m.goto(`${URL}/library/documents`); await m.waitForTimeout(1200);
  await m.screenshot({ path: `${OUT}/22-phone-docs.png` });
  const sw2 = await m.evaluate(() => document.documentElement.scrollWidth);
  ok(sw2 <= 390, `no page scroll on phone documents (${sw2})`);
  await m.goto(URL); await m.waitForTimeout(1200);
  await m.getByRole("button", { name: "Add photos and files" }).click(); await m.waitForTimeout(400);
  await m.screenshot({ path: `${OUT}/23-phone-menu.png` });

  ok(errors.length === 0, "no page errors: " + JSON.stringify(errors.slice(0, 5)));
  await b.close();
})();
