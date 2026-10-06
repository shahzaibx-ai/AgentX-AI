# UX and wording

Keep these when customising; they were checked on desktop, dark mode and a
390 px phone.

- **+ menu order:** Add files, Search Library ▸ (collections as checkboxes with
  document counts), separator, Add photos, Take a photo, hint "You can also
  paste photos or drop files." Button label "Add photos and files".
- **File chip:** type badge (PDF/DOCX…), name, status line: "Uploading · 42%"
  with a bar → "Reading the file…" → "36 KB · Ready"; errors in red on the chip
  ("This is a photo. Use Add photos for images.", "….exe files can't be read.
  Use PDF, Word, …", "The file is empty.", "40 MB is over the 25 MB limit. Split
  it, or ask a Library owner to add it to a collection."). × removes.
- **Library pill:** "Searching HR Policies ×" above the input; under a sent
  question: "Searching HR Policies". Pending reply: "Searching HR Policies and
  your files…" or "Reading your files…".
- **Send** is disabled while files upload or index ("Waiting for files to be
  ready"); the voice button is hidden while files are in the tray.
- **Answer:** `[n]` as small square buttons; a "Sources" box with number, type
  badge, title, "Page 2 · passage…"; the side panel shows the passage, where it
  came from and "Open original". Copy strips the markers.
- **Privacy line** under the composer: "Questions about files are answered by
  Gemini File Search (Google), only from the documents you picked." (offline:
  "Questions about files use offline test search on this server.")
- **Library pages:** sidebar link "Library" with an "Owner" badge; nav Overview,
  Documents, Collections, Retrieval test, Storage, Index settings (horizontal
  scroll on phones). Destructive actions confirm in a dialog that says what is
  lost. Empty states say what to do next.
- Neutral shadcn tokens, no gradients or decorative colour; status dots are
  the only colour (ready green, indexing amber, failed red).
