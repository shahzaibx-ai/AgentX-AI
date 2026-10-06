#!/usr/bin/env python3
"""Check that "Add files" and the Library work on a running app, and say what to fix.

    python doctor_library.py --api http://localhost:8000
    python doctor_library.py --api http://localhost:8000 --web http://localhost:3000 --ask
    python doctor_library.py --api https://api.example.com --token "$LIBRARY_TOKEN"

--ask uploads a tiny text file as a chat file, waits until it's indexed, asks
about it, checks the answer is cited, then deletes it. On Gemini this indexes a
few hundred bytes and makes one model request.

Standard library only. Exit code 1 if anything FAILs.
"""

from __future__ import annotations

import argparse
import json
import secrets
import time
import urllib.error
import urllib.request
import uuid

OK, WARN, FAIL = "ok  ", "warn", "FAIL"
failures = 0
NOTE = (
    "Doctor check note.\n\nThe lighthouse keeper's cat is called Biscuit and she is "
    "seven years old. The lighthouse was painted green in 2021.\n"
)


def report(status: str, label: str, detail: str = "") -> None:
    global failures
    failures += status == FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


def request(method, url, body=None, *, token="", timeout=30.0, raw=None, ctype=None):
    headers = {}
    data = None
    if raw is not None:
        data, headers["Content-Type"] = raw, ctype or "application/octet-stream"
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310 (your own URLs)
            return res.status, res.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def multipart(fields: dict[str, str], filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n".encode() + content + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


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


def check_api(base: str, token: str, ask: bool) -> None:
    print(f"API at {base}")
    try:
        status, body = request("GET", f"{base}/api/library/config")
    except (urllib.error.URLError, OSError) as exc:
        report(FAIL, "API not reachable", f"{exc}. Start it: cd api && uv run fastapi dev app/main.py")
        return
    if status == 404:
        report(FAIL, "Library not installed in the API", "no /api/library/config; run install_library.py")
        return
    check_voice(base)
    cfg = json.loads(body)
    if not cfg["enabled"]:
        reason = cfg.get("reason") or ""
        broken = "uv sync" in reason or "could not start" in reason
        report(FAIL if broken else WARN, "files and the Library are off", reason)
        print("        Set GEMINI_API_KEY (or RAG_ENGINE=offline for testing) in api/.env and restart.")
        return
    engine = "Gemini File Search" if cfg["engine"] == "gemini" else f"{cfg['engine']} (testing only)"
    report(OK if cfg["engine"] == "gemini" else WARN, "engine", f"{engine}, model {cfg['model']}")
    lim = cfg["limits"]
    report(
        OK,
        "limits",
        f"chat files {lim['chat_file_max_bytes'] // 1048576} MB × {lim['chat_files_per_message']}, "
        f"library files {lim['library_file_max_bytes'] // 1048576} MB, "
        f"chat files kept {lim['chat_file_retention_days'] or 'forever'} days",
    )
    report(OK, "collections people can search", ", ".join(c["name"] for c in cfg["collections"]) or "none yet")

    auth = cfg["owner_auth"]
    if auth == "open":
        report(WARN, "Library owner pages are open", "fine on your computer; set LIBRARY_TOKEN before deploying")
    elif auth == "disabled":
        report(WARN, "Library owner pages are locked", "production without LIBRARY_TOKEN; set it to manage the Library")
    else:
        status, _ = request("GET", f"{base}/api/library/overview")
        if status == 401:
            report(OK, "owner API needs the token")
        else:
            report(FAIL, "owner API answered without a token", f"HTTP {status}")

    if auth == "open" or (auth == "token" and token):
        status, body = request("GET", f"{base}/api/library/overview", token=token)
        if status == 200:
            ov = json.loads(body)
            if ov.get("store_error"):
                report(FAIL, "index", ov["store_error"])
            else:
                st = ov["totals"]["by_status"]
                report(
                    OK,
                    "index",
                    f"{st.get('indexed', 0)} ready, {st.get('queued', 0) + st.get('processing', 0)} indexing, "
                    f"queue {ov['queue']}",
                )
                if st.get("failed"):
                    report(WARN, f"{st['failed']} document(s) failed to index", "see Library → Documents → Failed")
        elif status == 401:
            report(FAIL, "owner token rejected", "check LIBRARY_TOKEN")
        else:
            report(FAIL, "overview", f"HTTP {status}: {body[:160]}")

    # Uploaded files must never run as pages on this site.
    status, _ = request("GET", f"{base}/api/files/{'0' * 32}/content")
    report(OK if status == 404 else FAIL, "unknown file ids are 404", f"HTTP {status}")

    if ask:
        ask_check(base)


def check_voice(base: str) -> None:
    """Voice mode (livekit-voice-mode) must keep working next to the Library."""
    status, body = request("GET", f"{base}/api/voice/config")
    if status == 404:
        return  # voice mode isn't installed
    if status != 200:
        report(FAIL, "voice mode", f"/api/voice/config HTTP {status}")
        return
    voice = json.loads(body)
    if voice.get("enabled"):
        report(OK, "voice mode is on", "the composer shows the voice button when it's empty")
    else:
        report(
            WARN,
            "voice mode is off",
            (voice.get("reason") or "")
            + " Check LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET in api/.env",
        )


def ask_check(base: str) -> None:
    chat_id = f"doctor-{secrets.token_hex(4)}"
    raw, ctype = multipart({"chat_id": chat_id}, "doctor-note.txt", NOTE.encode())
    status, body = request("POST", f"{base}/api/files", raw=raw, ctype=ctype, timeout=120)
    if status != 201:
        report(FAIL, "upload a chat file", f"HTTP {status}: {body[:200]}")
        return
    doc = json.loads(body)
    try:
        deadline = time.time() + 180
        while doc["status"] in {"queued", "processing"} and time.time() < deadline:
            time.sleep(2)
            doc = json.loads(request("GET", f"{base}/api/files/{doc['id']}")[1])
        if doc["status"] != "indexed":
            report(FAIL, "index a chat file", doc.get("error") or f"still {doc['status']} after 3 minutes")
            return
        report(OK, "chat file indexed")
        status, body = request(
            "POST",
            f"{base}/api/chat",
            {
                "messages": [{"role": "user", "content": "What is the lighthouse keeper's cat called?"}],
                "rag": {"files": [doc["id"]], "chat_id": chat_id},
            },
            timeout=180,
        )
        events = sse_events(body) if status == 200 else []
        err = next((d for e, d in events if e == "error"), None)
        src = next((d for e, d in events if e == "sources"), None)
        if status != 200 or err:
            report(FAIL, "answer from the file", (err or {}).get("message") or f"HTTP {status}")
        elif src and src["grounded"] and "Biscuit" in src["cited_text"]:
            report(OK, "answered from the file with citations", src["cited_text"][:80])
        else:
            report(FAIL, "answer not grounded", (src or {}).get("cited_text", "no sources event")[:120])
    finally:
        request("DELETE", f"{base}/api/files/{doc['id']}")


def check_web(url: str) -> None:
    print(f"Web at {url}")
    try:
        status, body = request("GET", f"{url}/api/library/config")
    except (urllib.error.URLError, OSError) as exc:
        report(FAIL, "web not reachable", f"{exc}. Start it: cd web && npm run dev")
        return
    if status != 200:
        report(FAIL, "web → API proxy", f"HTTP {status}; check API_URL for the web app")
        return
    report(OK, "web → API proxy")
    # 11 MB of an unsupported type: the API refuses it (415) once received. A proxy that
    # still has the 10 MB default cuts the upload off instead (500 / connection reset).
    raw, ctype = multipart({"chat_id": "doctor"}, "too-big.bin", b"0" * (11 * 1024 * 1024))
    try:
        status, _ = request("POST", f"{url}/api/files", raw=raw, ctype=ctype, timeout=120)
    except (urllib.error.URLError, OSError):
        status = 0
    if status in {415, 422, 503}:
        report(OK, "uploads over 10 MB pass the proxy")
    else:
        report(FAIL, "uploads over 10 MB fail at the proxy", f"HTTP {status}; set experimental.proxyClientMaxBodySize in next.config.ts")
    status, _ = request("GET", f"{url}/library")
    report(OK if status == 200 else FAIL, "Library pages", f"/library HTTP {status}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--web", help="web URL, e.g. http://localhost:3000")
    ap.add_argument("--token", default="", help="LIBRARY_TOKEN, to check the owner API")
    ap.add_argument("--ask", action="store_true", help="upload, index, ask and delete a tiny test file")
    args = ap.parse_args()
    print("Files and Library doctor")
    check_api(args.api.rstrip("/"), args.token, args.ask)
    if args.web:
        check_web(args.web.rstrip("/"))
    print("\nAll good." if not failures else f"\n{failures} problem(s) to fix.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
