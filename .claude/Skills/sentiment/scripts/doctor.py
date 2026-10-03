#!/usr/bin/env python3
"""Check a Sentiment Studio setup and say what to fix.

    python doctor.py                                   # tools only
    python doctor.py --api http://localhost:8000       # + running API, models, a prediction
    python doctor.py --api http://localhost:8000 --web http://localhost:3000 --load-all

Standard library only. Exit code 1 if anything FAILs.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request

OK, WARN, FAIL = "ok  ", "warn", "FAIL"
failures = 0


def report(status: str, label: str, detail: str = "") -> None:
    global failures
    failures += status == FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


def version(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out)
    return match.group(0) if match else None


def major(v: str | None) -> int:
    return int(v.split(".")[0]) if v else 0


def http(method: str, url: str, body: dict | None = None, timeout: float = 10.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310 (local URLs)
        return res.status, json.loads(res.read().decode() or "null")


def check_tools() -> None:
    print("tools")
    uv = version(["uv", "--version"])
    report(OK if uv else FAIL, "uv", uv or "install: https://docs.astral.sh/uv/")
    node = version(["node", "--version"])
    if not node:
        report(FAIL, "node", "install Node.js 24")
    elif major(node) < 24:
        report(WARN, "node", f"{node}; the project targets Node.js 24 (engines >=24)")
    else:
        report(OK, "node", node)
    npm = version(["npm", "--version"])
    report(OK if npm else FAIL, "npm", npm or "comes with Node.js")
    py = version(["uv", "python", "find", "3.12"])
    report(OK if py else WARN, "python 3.12", py or "uv will download it on `uv sync`")


def check_api(base: str, load_all: bool) -> None:
    print("api")
    base = base.rstrip("/")
    try:
        _, health = http("GET", f"{base}/api/health")
    except (urllib.error.URLError, OSError) as exc:
        report(FAIL, "API not reachable", f"{base}: {exc}. Start it: cd api && uv run fastapi dev")
        return
    report(OK, "API", f"v{health['version']} on {health['device']}")
    if health["device"] == "cpu":
        report(WARN, "device is CPU", "fine for light use; a GPU is much faster for batches and explanations")

    _, models = http("GET", f"{base}/api/models")
    for m in models["models"]:
        status = m["status"]
        mark = FAIL if status == "error" else OK
        detail = m["error"] if status == "error" else status.replace("_", " ")
        report(mark, f"{m['name']}{' (default)' if m['default'] else ''}", detail)

    targets = [m for m in models["models"] if load_all or m["default"]]
    for m in targets:
        if m["status"] != "ready":
            print(f"  … loading {m['name']} (first time downloads it)", flush=True)
        try:
            _, result = http(
                "POST",
                f"{base}/api/predict",
                {"text": "Great service, fast delivery.", "model": m["id"], "explain": False},
                timeout=900,
            )
            report(
                OK,
                f"predict · {m['name']}",
                f"{result['label']} {result['score']:.2f} in {result['latency_ms']:.0f} ms",
            )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            report(FAIL, f"predict · {m['name']}", f"HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, OSError) as exc:
            report(FAIL, f"predict · {m['name']}", str(exc))


def check_web(url: str) -> None:
    print("web")
    url = url.rstrip("/")
    try:
        with urllib.request.urlopen(url, timeout=10) as res:  # noqa: S310
            report(OK, "web app", f"{url} HTTP {res.status}")
    except (urllib.error.URLError, OSError) as exc:
        report(FAIL, "web app not reachable", f"{exc}. Start it: cd web && npm run dev")
        return
    try:
        http("GET", f"{url}/api/health")
        report(OK, "web → API proxy", "/api is forwarded")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        report(
            FAIL,
            "web → API proxy",
            f"{exc}. Check API_URL in web/.env.local (build time) and that the API runs",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", help="API base URL, e.g. http://localhost:8000")
    ap.add_argument("--web", help="web URL, e.g. http://localhost:3000")
    ap.add_argument("--load-all", action="store_true", help="load and test every enabled model")
    args = ap.parse_args()
    print("Sentiment Studio doctor")
    check_tools()
    if args.api:
        check_api(args.api, args.load_all)
    if args.web:
        check_web(args.web)
    print("\nAll good." if not failures else f"\n{failures} problem(s) to fix.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
