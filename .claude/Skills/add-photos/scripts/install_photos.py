#!/usr/bin/env python3
"""Install "Add photos" (image input for vision models) into a fullstack-ai-assistant project.

    python install_photos.py --project path/to/app            # install
    python install_photos.py --project path/to/app --dry-run  # show what would change

The project layout this targets (the fullstack-ai-assistant template, with or
without voice mode):

    api/   FastAPI app: app/main.py:create_app(), app/providers/*, app/services/chat.py
    web/   Next.js app: components/chat/chat-app.tsx, composer.tsx, hooks/use-chat.ts

What it does. Every step is safe to re-run:

1. Copies self-contained files: api/app/images.py, api/app/vision.py,
   api/app/core/body_limit.py, api/tests/test_photos.py, web/lib/images.ts,
   web/lib/image-store.ts, web/hooks/use-attachments.ts, web/hooks/use-image-url.ts
   and web/components/photos/. A file that already exists with different
   content is kept (reported) unless --force is given.
2. Applies anchored edits to the files that wire photos in (patches.py). An
   edit whose result is already present is skipped. If an edit's anchor is
   missing (the file was customised), that whole file is left unchanged (or,
   with --partial, the matching edits are applied) and reported as a manual
   step; references/manual-edits.md lists every edit by number. Projects with
   and without voice mode are both supported (two edit lists, chosen per file).
   README edits are optional: a customised README is only noted.

No new dependencies: resizing uses the browser's canvas, storage uses
IndexedDB, and the API decodes images with the standard library.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import argparse
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
    ("api/app/images.py", "api/app/images.py", "api"),
    ("api/app/vision.py", "api/app/vision.py", "api"),
    ("api/app/core/body_limit.py", "api/app/core/body_limit.py", "api"),
    ("api/tests/test_photos.py", "api/tests/test_photos.py", "api"),
    ("web/lib/images.ts", "web/lib/images.ts", "web"),
    ("web/lib/image-store.ts", "web/lib/image-store.ts", "web"),
    ("web/hooks/use-attachments.ts", "web/hooks/use-attachments.ts", "web"),
    ("web/hooks/use-image-url.ts", "web/hooks/use-image-url.ts", "web"),
    ("web/components/photos", "web/components/photos", "web"),
]
SKIP_NAMES = {"__pycache__", ".ruff_cache", ".pytest_cache", "node_modules"}
DOCS = {"README.md", "api/README.md", "web/README.md"}

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
        and (root / "api/app/providers/registry.py").exists(),
        "web": (root / "web/components/chat/chat-app.tsx").exists()
        and (root / "web/hooks/use-chat.ts").exists(),
    }


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
        part = file.split("/", 1)[0]
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
            rep.done.append(f"wired {file} ({applied} edit{'s' * (applied > 1)}, {name})")
        elif present == total:
            rep.same.append(f"{file} already wired")
        if failed:
            rep.manual.append(f"{file}: partly wired. Finish by hand: {where}")


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
    args = ap.parse_args()

    root = Path(args.project).resolve()
    found = detect(root)
    if not any(found.values()):
        print(f"No fullstack-ai-assistant layout found in {root}.")
        print("Expected api/app/main.py with create_app() and/or web/components/chat/chat-app.tsx.")
        print("For another stack, follow references/integrate-fastapi.md and references/integrate-react.md.")
        return 2
    if found["web"] and not found["api"] and "api" not in args.skip:
        print("note: the web part needs the API part (vision flags, image limits, image routing).")
    parts = {p for p, ok in found.items() if ok} - set(args.skip)
    for p, ok in found.items():
        if not ok and p not in args.skip:
            print(f"note: {p}/ not found or not the template layout; skipping it")

    rep = Report()
    print(f"Installing Add photos into {root}{'  (dry run)' if args.dry_run else ''}")
    copy_assets(root, parts, rep, args.dry_run, args.force)
    apply_edits(root, parts, rep, args.dry_run, args.partial)

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
        "  1. Install a model that can see images:  ollama pull gemma3   (or llava, qwen2.5vl)\n"
        "     or set a cloud key (Anthropic, OpenAI, Gemini) in api/.env\n"
        "  2. Restart the API and the web app (web: npm run build for production)\n"
        "  3. Check:  bash <skill>/scripts/verify_photos.sh .\n"
        "            python <skill>/scripts/doctor_photos.py --api http://localhost:8000\n"
    )
    return 1 if rep.manual else 0


if __name__ == "__main__":
    raise SystemExit(main())
