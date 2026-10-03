#!/usr/bin/env python3
"""Create a new Sentiment Studio project from the skill's template.

    python scaffold.py --dest ./acme-sentiment
    python scaffold.py --dest ./acme-sentiment --app-name "Acme Pulse" --user-name "Rizwan" \
        --description "Customer feedback sentiment for Acme" \
        --models finbert,sst2 --default-model finbert

Model short names: sst2 (DistilBERT SST-2), finbert (FinBERT), twitter (Twitter RoBERTa),
stars (Multilingual BERT 1-5 stars). Full Hugging Face ids work too. Default: all four,
DistilBERT SST-2 as default.

Standard library only; Python 3.10+. Refuses to write into an existing folder
unless --force.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"
TEMPLATE_NAME = "Sentiment Studio"
TEMPLATE_SLUG = "sentiment-studio"
TEMPLATE_USER = "Rizwan"
TEMPLATE_DESCRIPTION = "Sentiment analysis with PyTorch and Hugging Face Transformers."

MODELS = {
    "sst2": "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    "finbert": "ProsusAI/finbert",
    "twitter": "cardiffnlp/twitter-roberta-base-sentiment-latest",
    "stars": "nlptown/bert-base-multilingual-uncased-sentiment",
}
DEFAULT_MODEL = MODELS["sst2"]
SKIP = {"node_modules", ".next", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache"}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise SystemExit("--app-name must contain letters or digits")
    return slug


def resolve_model(token: str) -> str:
    token = token.strip()
    if token in MODELS:
        return MODELS[token]
    if token in MODELS.values():
        return token
    raise SystemExit(f"Unknown model {token!r}. Use one of: {', '.join(MODELS)} (or their ids)")


def replace_in(path: Path, pairs: list[tuple[str, str]], *, required: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in text:
            if required:
                raise SystemExit(f"template drift: {old!r} not found in {path}")
            continue
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def ts_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", required=True, help="new project folder")
    ap.add_argument("--app-name", default=TEMPLATE_NAME)
    ap.add_argument("--user-name", default=TEMPLATE_USER, help="placeholder user shown in the UI")
    ap.add_argument("--description", default=TEMPLATE_DESCRIPTION)
    ap.add_argument("--models", default=",".join(MODELS), help="comma list: sst2,finbert,twitter,stars")
    ap.add_argument("--default-model", default=None, help="one of --models (default: first of them)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing folder")
    args = ap.parse_args(argv)

    dest = Path(args.dest).resolve()
    if dest.exists() and any(dest.iterdir()):
        if not args.force:
            print(f"{dest} exists and is not empty. Use --force to overwrite it.", file=sys.stderr)
            return 1
        shutil.rmtree(dest)

    models = list(dict.fromkeys(resolve_model(t) for t in args.models.split(",") if t.strip()))
    if not models:
        raise SystemExit("--models must list at least one model")
    default = (
        resolve_model(args.default_model)
        if args.default_model
        else (DEFAULT_MODEL if DEFAULT_MODEL in models else models[0])
    )
    if default not in models:
        raise SystemExit("--default-model must be one of --models")

    name, slug = args.app_name.strip(), slugify(args.app_name)
    shutil.copytree(TEMPLATE, dest, ignore=shutil.ignore_patterns(*SKIP))
    api, web = dest / "api", dest / "web"

    # Package names (manifests and lockfiles stay consistent).
    replace_in(api / "pyproject.toml", [(f'name = "{TEMPLATE_SLUG}-api"', f'name = "{slug}-api"')])
    replace_in(api / "uv.lock", [(f'name = "{TEMPLATE_SLUG}-api"', f'name = "{slug}-api"')])
    for file in (web / "package.json", web / "package-lock.json"):
        replace_in(file, [(f'"name": "{TEMPLATE_SLUG}-web"', f'"name": "{slug}-web"')])

    # Branding.
    replace_in(
        web / "lib" / "config.ts",
        [
            (f'appName: "{TEMPLATE_NAME}"', f"appName: {ts_string(name)}"),
            (f'appDescription: "{TEMPLATE_DESCRIPTION}"', f"appDescription: {ts_string(args.description)}"),
            (f'user: {{ name: "{TEMPLATE_USER}" }}', f"user: {{ name: {ts_string(args.user_name)} }}"),
        ],
    )
    replace_in(
        web / "lib" / "storage.ts",
        [
            (f'"{TEMPLATE_SLUG}.model.v1"', f'"{slug}.model.v1"'),
            (f'"{TEMPLATE_SLUG}.history.v1"', f'"{slug}.history.v1"'),
        ],
    )
    replace_in(
        api / "app" / "core" / "config.py",
        [(f'app_name: str = "{TEMPLATE_NAME} API"', f"app_name: str = {json.dumps(name + ' API')}")],
    )
    replace_in(api / "app" / "__init__.py", [(f'"""{TEMPLATE_NAME} API."""', f'"""{name} API."""')])
    replace_in(
        dest / "README.md", [(f"# {TEMPLATE_NAME}\n", f"# {name}\n"), (f"{TEMPLATE_SLUG}/\n", f"{slug}/\n")]
    )
    replace_in(
        dest / "CLAUDE.md",
        [(f"# {TEMPLATE_NAME}\n", f"# {name}\n"), (f"**{TEMPLATE_USER}**", f"**{args.user_name}**")],
    )
    replace_in(api / "README.md", [(f"# {TEMPLATE_NAME} API", f"# {name} API")])
    replace_in(web / "README.md", [(f"# {TEMPLATE_NAME} web", f"# {name} web")])

    # Local config files (git-ignored) from the examples.
    env = (api / ".env.example").read_text(encoding="utf-8")
    if models != list(MODELS.values()) or default != DEFAULT_MODEL:
        env += (
            "\n# ---------- Chosen at scaffold time ----------\n"
            f"ENABLED_MODELS={json.dumps(models)}\n"
            f"DEFAULT_MODEL={default}\n"
            f"PRELOAD_MODELS={json.dumps([default])}\n"
        )
    (api / ".env").write_text(env, encoding="utf-8")
    shutil.copyfile(web / ".env.example", web / ".env.local")

    short = {v: k for k, v in MODELS.items()}
    print(
        f"Created {name} in {dest}\n"
        f"  packages: {slug}-api, {slug}-web\n"
        f"  models:   {', '.join(short[m] for m in models)} (default: {short[default]})\n"
        f"  user:     {args.user_name}\n\n"
        f"Next:\n"
        f"  cd {dest}/api && uv sync && uv run fastapi dev\n"
        f"  cd {dest}/web && npm install && npm run dev\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
