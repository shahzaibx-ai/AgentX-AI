#!/usr/bin/env python3
"""Scaffold a new full-stack AI assistant project from the bundled template.

Usage:
    python scaffold.py --dest ./acme-assistant --app-name "Acme Copilot"
    python scaffold.py --dest ./demo --app-name "Helpdesk AI" --user-name "Rizwan" --force

Only the Python standard library is used, so this runs anywhere Python 3.9+ exists.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"

TEMPLATE_SLUG = "ai-assistant"
TEMPLATE_APP_NAME = "Assistant"
TEMPLATE_USER = "Rizwan"
TEMPLATE_DESCRIPTION = "AI assistant powered by local and cloud models"

IGNORE = shutil.ignore_patterns(
    "node_modules", ".next", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
    "tsconfig.tsbuildinfo", "next-env.d.ts", ".env", ".env.local",
)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "ai-assistant"


def ts_string(value: str) -> str:
    """Quote a value as a TypeScript/JSON string literal."""
    return json.dumps(value, ensure_ascii=False)


def replace_in(path: Path, replacements: list[tuple[str, str]], *, regex: bool = False) -> None:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        if regex:
            text, count = re.subn(old, lambda _m, n=new: n, text)
        else:
            count = text.count(old)
            text = text.replace(old, new)
        if count == 0:
            raise SystemExit(f"scaffold: expected to find {old!r} in {path}; template changed?")
    if text != original:
        path.write_text(text, encoding="utf-8")


def customise(root: Path, app_name: str, slug: str, user_name: str, description: str) -> None:
    web, api = root / "web", root / "api"

    # Frontend display settings: the single place the UI reads names from.
    replace_in(
        web / "lib" / "config.ts",
        [
            (f"appName: {ts_string(TEMPLATE_APP_NAME)}", f"appName: {ts_string(app_name)}"),
            (f"appDescription: {ts_string(TEMPLATE_DESCRIPTION)}",
             f"appDescription: {ts_string(description)}"),
            (f"name: {ts_string(TEMPLATE_USER)}", f"name: {ts_string(user_name)}"),
        ],
    )

    # Package names (lockfiles too, so `npm ci` and `uv sync --frozen` keep working).
    for file in (web / "package.json", web / "package-lock.json"):
        replace_in(file, [(f'"name": "{TEMPLATE_SLUG}-web"', f'"name": "{slug}-web"')])
    for file in (api / "pyproject.toml", api / "uv.lock"):
        replace_in(file, [(f'name = "{TEMPLATE_SLUG}-api"', f'name = "{slug}-api"')])

    replace_in(
        api / "app" / "core" / "config.py",
        [('app_name: str = "AI Assistant API"', f"app_name: str = {json.dumps(app_name + ' API')}")],
    )
    replace_in(root / "README.md", [("# AI Assistant — Full Stack", f"# {app_name} — Full Stack")])

    # Ready-to-edit env files.
    shutil.copyfile(api / ".env.example", api / ".env")
    shutil.copyfile(web / ".env.example", web / ".env.local")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--dest", required=True, type=Path, help="Folder to create")
    parser.add_argument("--app-name", default=TEMPLATE_APP_NAME, help="Name shown in the UI")
    parser.add_argument("--slug", help="Package name prefix (default: from --app-name)")
    parser.add_argument("--user-name", default=TEMPLATE_USER, help="Placeholder user shown in the UI")
    parser.add_argument("--description", default=TEMPLATE_DESCRIPTION, help="HTML meta description")
    parser.add_argument("--force", action="store_true", help="Replace --dest if it exists")
    args = parser.parse_args()

    if not TEMPLATE.is_dir():
        print(f"scaffold: template not found at {TEMPLATE}", file=sys.stderr)
        return 1

    dest: Path = args.dest.resolve()
    if dest.exists():
        if not args.force:
            print(f"scaffold: {dest} already exists (use --force to replace it)", file=sys.stderr)
            return 1
        shutil.rmtree(dest)

    slug = slugify(args.slug or args.app_name)
    if args.app_name == TEMPLATE_APP_NAME and not args.slug:
        slug = TEMPLATE_SLUG

    shutil.copytree(TEMPLATE, dest, ignore=IGNORE)
    customise(dest, args.app_name, slug, args.user_name, args.description)

    print(f"""
Created {args.app_name} at {dest}
  packages: {slug}-api, {slug}-web
  user:     {args.user_name} (placeholder, edit web/lib/config.ts)

Next steps:
  ollama pull llama3.2                     # optional local model
  cd {dest}/api && uv sync && uv run fastapi dev app/main.py
  cd {dest}/web && npm install && npm run dev
  add cloud keys to api/.env for fallback, then open http://localhost:3000
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
