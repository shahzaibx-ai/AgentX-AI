#!/usr/bin/env python3
"""Install "Add files" and the Library (RAG with citations) into a fullstack-ai-assistant project.

    python install_library.py --project path/to/app            # install
    python install_library.py --project path/to/app --dry-run  # show what would change

Targets the fullstack-ai-assistant template with photos (the add-photos skill),
with or without voice mode:

    api/   FastAPI app: app/main.py:create_app(), app/images.py, app/routes/chat.py
    web/   Next.js app: components/chat/chat-app.tsx, composer.tsx, components/photos/

What it does. Every step is safe to re-run:

1. Copies self-contained files: api/app/library/ (engine protocol, Gemini File
   Search and offline engines, citations, SQLite records, service, routes),
   api/app/library_chat.py, the tests and fixtures, and on the web side
   app/library/, components/files/, components/library/, components/ui/dialog.tsx,
   hooks/use-chat-files.ts, hooks/use-library-config.ts, lib/library.ts and
   lib/library-admin.ts. A file that already exists with different content is
   kept (reported) unless --force is given.
2. Applies anchored edits to the files that wire it in (patches.py, or
   patches_no_voice.py for projects without voice mode; chosen per file). An
   edit whose result is already present is skipped. If an edit's anchor is
   missing (the file was customised), that file is left unchanged (or, with
   --partial, the matching edits are applied) and reported; every edit is listed
   by number in references/manual-edits.md. README edits are optional.
3. Updates api/uv.lock with `uv lock` and installs it with `uv sync` (new
   dependency: google-genai; dev: pypdf, python-docx for the offline engine).
   Use --no-lock to skip.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.path.insert(0, str(HERE))

from patches import EDITS  # noqa: E402
from patches_no_voice import EDITS as EDITS_NO_VOICE  # noqa: E402

# Projects with and without voice mode differ in the chat UI files, so each
# wired file is matched against both edit lists and the one that fits is used.
VARIANTS = [("with voice mode", EDITS), ("without voice mode", EDITS_NO_VOICE)]

COPY = [
    # (asset path, project path, part)
    ("api/app/library", "api/app/library", "api"),
    ("api/app/library_chat.py", "api/app/library_chat.py", "api"),
    ("api/tests/test_library.py", "api/tests/test_library.py", "api"),
    ("api/tests/test_library_gemini.py", "api/tests/test_library_gemini.py", "api"),
    ("api/tests/fake_gemini_api.py", "api/tests/fake_gemini_api.py", "api"),
    ("api/tests/fixtures/library", "api/tests/fixtures/library", "api"),
    ("web/app/library", "web/app/library", "web"),
    ("web/components/files", "web/components/files", "web"),
    ("web/components/library", "web/components/library", "web"),
    ("web/components/ui/dialog.tsx", "web/components/ui/dialog.tsx", "web"),
    ("web/hooks/use-chat-files.ts", "web/hooks/use-chat-files.ts", "web"),
    ("web/hooks/use-library-config.ts", "web/hooks/use-library-config.ts", "web"),
    ("web/lib/library.ts", "web/lib/library.ts", "web"),
    ("web/lib/library-admin.ts", "web/lib/library-admin.ts", "web"),
]
SKIP_NAMES = {"__pycache__", ".ruff_cache", ".pytest_cache", "node_modules"}
DOCS = {"README.md", "api/README.md", "web/README.md"}
# Outside api/ and web/ but part of the API's deployment.
PART_OF = {"docker-compose.yml": "api"}

GUIDE_API = "references/integrate-fastapi.md"
GUIDE_WEB = "references/integrate-react.md"


@dataclass
class Report:
    done: list[str] = field(default_factory=list)
    same: list[str] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write(path: Path, text: str, dry: bool) -> None:
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def detect(root: Path) -> dict[str, bool]:
    main = root / "api/app/main.py"
    return {
        "api": main.exists()
        and "def create_app" in read(main)
        and (root / "api/app/routes/chat.py").exists(),
        "web": (root / "web/components/chat/chat-app.tsx").exists()
        and (root / "web/hooks/use-chat.ts").exists(),
    }


def has_photos(root: Path, parts: set[str]) -> list[str]:
    """The Library builds on the photo feature's + menu, drop zone and body limit."""
    missing = []
    if "api" in parts and not (root / "api/app/core/body_limit.py").exists():
        missing.append("api/app/core/body_limit.py")
    if "web" in parts and not (root / "web/components/photos/drop-overlay.tsx").exists():
        missing.append("web/components/photos/drop-overlay.tsx")
    return missing


def iter_files(src: Path):
    if src.is_file():
        yield src, Path()
        return
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if path.is_file() and not SKIP_NAMES.intersection(rel.parts):
            yield path, rel


def copy_assets(root: Path, parts: set[str], rep: Report, dry: bool, force: bool) -> None:
    for asset, target, part in COPY:
        if part not in parts:
            continue
        added = changed = kept = 0
        for path, rel in iter_files(ASSETS / asset):
            dest = root / target / rel if rel.parts else root / target
            data = path.read_bytes()
            if dest.exists():
                if dest.read_bytes() == data:
                    continue
                if not force:
                    kept += 1
                    rep.manual.append(
                        f"{dest.relative_to(root)} exists and differs; kept yours (use --force to replace)"
                    )
                    continue
                changed += 1
            else:
                added += 1
            if not dry:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
        if added or changed:
            rep.done.append(f"copied {target} ({added} new, {changed} replaced)")
        elif not kept:
            rep.same.append(f"{target} already present")


def simulate(text: str, edits: list[tuple[str, str]]) -> tuple[str, int, int, list[str]]:
    applied, present, failed = 0, 0, []
    for i, (old, new) in enumerate(edits, 1):
        if new in text:
            present += 1
        elif text.count(old) == 1:
            text = text.replace(old, new)
            applied += 1
        else:
            failed.append(str(i))
    return text, applied, present, failed


def apply_edits(root: Path, parts: set[str], rep: Report, dry: bool, partial: bool) -> None:
    per_variant: list[tuple[str, dict[str, list[tuple[str, str]]]]] = []
    for name, edits in VARIANTS:
        by_file: dict[str, list[tuple[str, str]]] = {}
        for file, old, new in edits:
            by_file.setdefault(file, []).append((old, new))
        per_variant.append((name, by_file))
    files = list(dict.fromkeys(f for _, by_file in per_variant for f in by_file))

    for file in files:
        part = PART_OF.get(file, file.split("/", 1)[0])
        doc = file in DOCS
        if not doc and part not in parts:
            continue
        path = root / file
        guide = GUIDE_API if part == "api" else GUIDE_WEB
        if not path.exists():
            (rep.notes if doc else rep.manual).append(f"{file}: not found" + ("" if doc else f"; see {guide}"))
            continue
        original = read(path)
        # The first variant whose edits all fit wins; otherwise the closest one.
        results = []
        for name, by_file in per_variant:
            if file in by_file:
                edits = by_file[file]
                results.append((name, len(edits), *simulate(original, edits)))
        name, total, text, applied, present, failed = min(results, key=lambda r: len(r[5]))
        # Most files get the same edits with or without voice mode: don't name a variant.
        if len({tuple(by_file.get(file, ())) for _, by_file in per_variant}) == 1:
            name = "same with or without voice"
        where = f"references/manual-edits.md ({name}: {file}, edit {', '.join(failed)} of {total})"
        if doc and failed:
            if applied and partial:
                write(path, text, dry)
            rep.notes.append(f"{file}: customised, docs not updated (optional; see {where})")
            continue
        if failed and not partial:
            # A half-wired file may not compile, so leave it exactly as it was.
            rep.manual.append(f"{file}: customised, left unchanged. Apply by hand: {where} and {guide}")
            continue
        if applied:
            write(path, text, dry)
            label = name if name.startswith("same") else f"{name} edit list"
            rep.done.append(f"wired {file} ({applied} edit{'s' * (applied > 1)}, {label})")
        elif present == total:
            rep.same.append(f"{file} already wired")
        if failed:
            rep.manual.append(f"{file}: partly wired. Finish by hand: {where}")


def lock(api: Path, rep: Report) -> None:
    """Refresh uv.lock and install the new dependencies (needs network to PyPI).

    Installing matters: with GEMINI_API_KEY set the Library starts on its own, and
    without google-genai in the API's environment it would be off (it never stops
    the API, but the feature would be missing until `uv sync`).
    """
    uv = shutil.which("uv")
    if not uv:
        rep.manual.append("uv not found: run `uv sync` in api/ to install google-genai")
        return
    if (api / "uv.lock").exists():
        check = subprocess.run([uv, "lock", "--check"], cwd=api, capture_output=True, check=False)
        if check.returncode == 0:
            rep.same.append("api/uv.lock up to date")
        else:
            res = subprocess.run([uv, "lock"], cwd=api, capture_output=True, text=True, check=False)
            if res.returncode != 0:
                tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["unknown error"]
                rep.manual.append(f"`uv lock` failed in api/ ({tail[0]}); run `uv sync` when online")
                return
            rep.done.append("updated api/uv.lock (google-genai; dev: pypdf, python-docx)")
    res = subprocess.run([uv, "sync", "--quiet"], cwd=api, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        rep.done.append("installed api dependencies (uv sync)")
    else:
        tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["unknown error"]
        rep.manual.append(f"`uv sync` failed in api/ ({tail[0]}); run it before restarting the API")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="project root containing api/ and web/")
    ap.add_argument("--dry-run", action="store_true", help="report changes without writing")
    ap.add_argument("--force", action="store_true", help="replace copied files that you changed")
    ap.add_argument(
        "--partial",
        action="store_true",
        help="apply the edits that match even when others in the same file do not",
    )
    ap.add_argument(
        "--skip", action="append", default=[], choices=["api", "web"], help="leave a part out"
    )
    ap.add_argument(
        "--no-lock", action="store_true", help="don't run `uv lock` / `uv sync` in api/"
    )
    args = ap.parse_args()

    root = Path(args.project).resolve()
    found = detect(root)
    if not any(found.values()):
        print(f"No fullstack-ai-assistant layout found in {root}.")
        print("Expected api/app/main.py with create_app() and/or web/components/chat/chat-app.tsx.")
        print("For another stack, follow references/integrate-fastapi.md and references/integrate-react.md.")
        return 2
    if found["web"] and not found["api"] and "api" not in args.skip:
        print("note: the web part needs the API part (/api/files, /api/library/*, rag in /api/chat).")
    parts = {p for p, ok in found.items() if ok} - set(args.skip)
    for p, ok in found.items():
        if not ok and p not in args.skip:
            print(f"note: {p}/ not found or not the template layout; skipping it")

    missing = has_photos(root, parts)
    if missing:
        print("The Library builds on Add photos (the + menu, drop zone and body-size limit),")
        print(f"which isn't installed here ({', '.join(missing)} missing).")
        print("Install it first with the add-photos skill, then run this again.")
        return 2

    rep = Report()
    print(f"Installing Add files + Library into {root}{'  (dry run)' if args.dry_run else ''}")
    copy_assets(root, parts, rep, args.dry_run, args.force)
    apply_edits(root, parts, rep, args.dry_run, args.partial)
    if "api" in parts and not args.dry_run and not args.no_lock:
        lock(root / "api", rep)

    print()
    for line in rep.done:
        print(f"  ✓ {line}")
    for line in rep.same:
        print(f"  · {line}")
    for line in rep.manual:
        print(f"  ! {line}")
    for line in rep.notes:
        print(f"  i {line}")
    print(
        "\nNext:\n"
        "  1. api/.env: GEMINI_API_KEY=...  (Gemini File Search)\n"
        "     or RAG_ENGINE=offline to try it without a key; LIBRARY_TOKEN=... for production\n"
        "  2. Restart the API and the web app. Start the API with `uv run …` (or run\n"
        "     `uv sync` first): its environment needs the new google-genai package\n"
        "  3. Check:  bash <skill>/scripts/verify_library.sh .\n"
        "            python <skill>/scripts/doctor_library.py --api http://localhost:8000\n"
    )
    return 1 if rep.manual else 0


if __name__ == "__main__":
    raise SystemExit(main())
