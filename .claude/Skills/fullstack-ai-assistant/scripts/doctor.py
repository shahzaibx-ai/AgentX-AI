#!/usr/bin/env python3
"""Check a machine (or a running stack) is ready for the AI assistant.

    python doctor.py                         # tools + Ollama
    python doctor.py --api http://localhost:8000 --web http://localhost:3000

Reports each check as OK / WARN / FAIL with a one-line fix. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

OK, WARN, FAIL = "\033[32mOK  \033[0m", "\033[33mWARN\033[0m", "\033[31mFAIL\033[0m"
failures = 0


def report(status: str, label: str, detail: str = "") -> None:
    global failures
    failures += status == FAIL
    print(f"  {status} {label}{' — ' + detail if detail else ''}")


def version_of(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", out)
    return match.group(1) if match else out.strip() or None


def at_least(version: str | None, minimum: tuple[int, ...]) -> bool:
    if not version:
        return False
    parts = tuple(int(p) for p in version.split(".")[: len(minimum)])
    return parts >= minimum


def get_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as res:  # noqa: S310 - local URLs
        return json.loads(res.read())


def check_tools() -> None:
    print("Tools")
    uv = version_of(["uv", "--version"])
    report(OK if uv else FAIL, f"uv {uv or 'not found'}",
           "" if uv else "install: https://docs.astral.sh/uv/getting-started/installation/")
    node = version_of(["node", "--version"])
    report(OK if at_least(node, (20, 9)) else FAIL, f"Node.js {node or 'not found'}",
           "" if at_least(node, (20, 9)) else "Next.js 16 needs Node.js 20.9 or newer")
    npm = version_of(["npm", "--version"])
    report(OK if npm else FAIL, f"npm {npm or 'not found'}")
    ollama = version_of(["ollama", "--version"])
    report(OK if ollama else WARN, f"Ollama CLI {ollama or 'not found'}",
           "" if ollama else "optional; install from https://ollama.com for local models")


def check_ollama(host: str) -> None:
    print(f"Ollama at {host}")
    try:
        tags = get_json(f"{host.rstrip('/')}/api/tags")
    except (urllib.error.URLError, OSError, ValueError):
        report(WARN, "not reachable", "start it with `ollama serve` (cloud fallback still works)")
        return
    names = [m.get("model") or m.get("name") for m in tags.get("models", [])]
    chat = [n for n in names if n and "embed" not in n]
    if chat:
        report(OK, f"{len(chat)} chat model(s)", ", ".join(chat[:6]))
    else:
        report(WARN, "running but no chat models", "run `ollama pull llama3.2`")


def check_api(url: str) -> None:
    print(f"API at {url}")
    try:
        health = get_json(f"{url.rstrip('/')}/api/health")
        report(OK, f"health {health.get('status')} (v{health.get('version')})")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        report(FAIL, "not reachable", f"{exc}; start with `uv run fastapi dev app/main.py`")
        return
    try:
        models = get_json(f"{url.rstrip('/')}/api/models?refresh=true", timeout=20)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        report(FAIL, "/api/models failed", str(exc))
        return
    for p in models["providers"]:
        if p["available"]:
            report(OK, p["label"], f"{len(p['models'])} model(s)")
        elif p["configured"]:
            report(WARN, p["label"], p.get("error") or "unavailable")
    default = models.get("default")
    if default:
        report(OK, "default model", f"{default['provider']}/{default['id']}")
    else:
        report(FAIL, "no model available", "pull an Ollama model or add a cloud key to api/.env")


def check_web(url: str) -> None:
    print(f"Web at {url}")
    try:
        get_json(f"{url.rstrip('/')}/api/health")
        report(OK, "proxy to API works")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        report(FAIL, "/api proxy failed", f"{exc}; check API_URL in web/.env.local")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama", default="http://localhost:11434")
    parser.add_argument("--api", help="Running API base URL to check")
    parser.add_argument("--web", help="Running web base URL to check")
    args = parser.parse_args()

    check_tools()
    check_ollama(args.ollama)
    if args.api:
        check_api(args.api)
    if args.web:
        check_web(args.web)
    print("\nAll required checks passed." if not failures else f"\n{failures} check(s) failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
