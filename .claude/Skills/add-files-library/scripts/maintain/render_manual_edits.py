"""Render references/manual-edits.md from scripts/patches.py and scripts/patches_no_voice.py.

    python scripts/maintain/render_manual_edits.py
"""

import difflib
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from patches import EDITS  # noqa: E402
from patches_no_voice import EDITS as EDITS_NO_VOICE  # noqa: E402

out = [
    "# Manual edits",
    "",
    "Every edit `install_library.py` makes to existing files, numbered the way its",
    "report numbers them. Use this when the installer says a file was customised:",
    "find the variant, file and edit number, then make the `+` lines appear where",
    "the unchanged (space-prefixed) lines point. Lines starting with `-` are",
    "replaced. Generated from `scripts/patches*.py`; do not edit by hand.",
    "",
    "The installer reports which variant it matched: **with voice mode** or",
    "**without voice mode**. Most API edits are the same in both.",
    "",
    "What each file gets, in one line:",
    "",
    "| File | Change |",
    "|---|---|",
    "| `api/pyproject.toml` | `google-genai` dependency; dev `pypdf`, `python-docx`; ruff per-file ignores; a pytest warning filter |",
    "| `api/.env.example` | Files and the Library block (`RAG_*`, `LIBRARY_*`, chat file limits) |",
    "| `api/.gitignore`, `api/Dockerfile`, `docker-compose.yml` | `data/` ignored; writable `/app/data/library`; a `library` volume |",
    "| `api/app/main.py` | `create_app(library_settings=, library_engine=)`, PATCH/DELETE in CORS, body limits for uploads, `mount_library` + its lifespan |",
    "| `api/app/schemas.py` | `RagScope` (collections, files, chat_id) and `ChatRequest.rag` |",
    "| `api/app/routes/chat.py` | requests with `rag` go to `rag_chat_events` |",
    "| `api/tests/conftest.py` | `library_settings` fixture; `make_client(library=, library_engine=)` |",
    "| `web/next.config.ts` | rewrite body limit 110 MB, proxy timeout 120 s |",
    "| `web/lib/types.ts` | `ChatFile`, `CollectionRef`, `Citation`; message `files`/`collections`/`sources`; conversation `collections` |",
    "| `web/lib/api.ts` | exports `API_BASE`, `errorMessage`; `rag` in the request; `sources` event |",
    "| `web/hooks/use-chat.ts` | `send(text, {images, files, collections, newChatId})`, `ragFor`, citations, `setCollections` |",
    "| `web/components/ui/dropdown-menu.tsx` | `DropdownMenuCheckboxItem` |",
    "| `web/components/photos/drop-overlay.tsx` | optional `title` |",
    "| `web/components/chat/markdown.tsx` | `[n]` markers become citation buttons |",
    "| `web/components/chat/composer.tsx` | Add files, Search Library sub-menu, file chips, Library pills, `onSend(text)` |",
    "| `web/components/chat/message*.tsx` | file chips, \"Searching …\", Sources + passage panel, notices |",
    "| `web/components/chat/app-sidebar.tsx` | Library link (Owner), paperclip on chats with files |",
    "| `web/components/chat/chat-app.tsx` | draft chat id, file tray, collections per chat, drop routing, delete-with-undo purge, privacy line |",
    "| `README.md`, `api/README.md`, `web/README.md` | docs (optional) |",
    "",
]


def section(title: str, edits) -> None:
    files: dict[str, list[tuple[str, str]]] = {}
    for f, old, new in edits:
        files.setdefault(f, []).append((old, new))
    out.append(f"# {title}")
    out.append("")
    out.append("Files: " + ", ".join(f"`{f}` ({len(e)})" for f, e in files.items()))
    out.append("")
    for f, file_edits in files.items():
        out.append(f"## {f}")
        out.append("")
        for i, (old, new) in enumerate(file_edits, 1):
            diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=50)
            body = [ln for ln in diff if not ln.startswith(("---", "+++", "@@"))]
            out.append(f"**Edit {i} of {len(file_edits)}**")
            out.append("")
            out.append("```diff")
            out.extend(body)
            out.append("```")
            out.append("")


section("With voice mode", EDITS)
section("Without voice mode", EDITS_NO_VOICE)
(SKILL / "references" / "manual-edits.md").write_text("\n".join(out))
print("wrote references/manual-edits.md")
