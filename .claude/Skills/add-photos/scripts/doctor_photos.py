#!/usr/bin/env python3
"""Check that "Add photos" works on a running app, and say what to fix.

    python doctor_photos.py --api http://localhost:8000
    python doctor_photos.py --api http://localhost:8000 --web http://localhost:3000 --send

--send also posts a small test photo through /api/chat (uses a model; on a
cloud model it costs a request).

Standard library only. Exit code 1 if anything FAILs.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

OK, WARN, FAIL = "ok  ", "warn", "FAIL"
failures = 0
# A 1x1 PNG.
PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def report(status: str, label: str, detail: str = "") -> None:
    global failures
    failures += status == FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


def request(method: str, url: str, body: dict | None = None, timeout: float = 30.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310 (local URLs)
            return res.status, res.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def sse_events(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events


def check_api(base: str, send: bool) -> None:
    print(f"API at {base}")
    try:
        status, body = request("GET", f"{base}/api/models?refresh=true")
    except (urllib.error.URLError, OSError) as exc:
        report(FAIL, "API not reachable", f"{exc}. Start it: cd api && uv run fastapi dev app/main.py")
        return
    models = json.loads(body)
    limits = models.get("image_limits")
    if limits is None:
        report(FAIL, "photos not installed in the API", "no image_limits in /api/models; run install_photos.py")
        return
    mb = limits["max_bytes"] / 1024 / 1024
    report(OK, "limits", f"{limits['per_message']}/message, {limits['per_request']}/request, {mb:g} MB each")

    seeing = [
        f"{p['id']}/{m['id']}" for p in models["providers"] for m in p["models"] if m.get("vision")
    ]
    blind = [f"{p['id']}/{m['id']}" for p in models["providers"] for m in p["models"] if not m.get("vision")]
    if seeing:
        report(OK, "models that can see images", ", ".join(seeing[:8]) + (" …" if len(seeing) > 8 else ""))
    else:
        report(
            WARN,
            "no model can see images",
            "photos will be refused. Run `ollama pull gemma3` (or llava, qwen2.5vl) or add a cloud key",
        )
    if blind:
        report(OK, "text-only models", ", ".join(blind[:6]) + (" …" if len(blind) > 6 else ""))
    vision = models.get("default_vision")
    if vision:
        report(OK, "Auto with photos uses", f"{vision['provider']}/{vision['id']}")

    # The server must refuse a *string path* as image data (the Ollama SDK would read the file).
    status, body = request(
        "POST",
        f"{base}/api/chat",
        {"messages": [{"role": "user", "content": "x", "images": [{"media_type": "image/png", "data": "/etc/passwd"}]}]},
    )
    if status == 422:
        report(OK, "rejects non-image data", "a file path is not accepted as a photo")
    else:
        report(FAIL, "accepted a file path as a photo", f"HTTP {status}; the API must decode and sniff images")

    if not send:
        return
    status, body = request(
        "POST",
        f"{base}/api/chat",
        {"messages": [{"role": "user", "content": "What colour is this pixel? One word.",
                       "images": [{"media_type": "image/png", "data": PNG}]}]},  # fmt: skip
        timeout=180,
    )
    if status != 200:
        report(FAIL, "test photo", f"HTTP {status}: {body[:200]}")
        return
    events = sse_events(body)
    meta = next((d for e, d in events if e == "meta"), None)
    error = next((d for e, d in events if e == "error"), None)
    if error:
        report(WARN if not seeing else FAIL, "test photo", error["message"])
    elif meta:
        text = "".join(d.get("delta", "") for e, d in events if e == "message")
        report(OK, "test photo answered", f"{meta['provider']}/{meta['model']}: {text.strip()[:60]!r}")


def check_web(url: str) -> None:
    print(f"Web at {url}")
    try:
        status, body = request("GET", f"{url}/api/models")
    except (urllib.error.URLError, OSError) as exc:
        report(FAIL, "web not reachable", f"{exc}. Start it: cd web && npm run dev")
        return
    if status == 200 and "image_limits" in body:
        report(OK, "web → API proxy", "the web app gets photo limits and vision flags")
    else:
        report(FAIL, "web → API proxy", f"HTTP {status}; check API_URL for the web app")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--web", help="web URL, e.g. http://localhost:3000")
    ap.add_argument("--send", action="store_true", help="send a 1x1 test photo through /api/chat")
    args = ap.parse_args()
    print("Add photos doctor")
    check_api(args.api.rstrip("/"), args.send)
    if args.web:
        check_web(args.web.rstrip("/"))
    print("\nAll good." if not failures else f"\n{failures} problem(s) to fix.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
