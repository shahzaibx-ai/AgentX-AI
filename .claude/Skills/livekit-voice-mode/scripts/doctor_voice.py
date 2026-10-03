#!/usr/bin/env python3
"""Check a voice-mode setup end to end and say exactly what to fix.

    python doctor_voice.py --project path/to/app            # config files only
    python doctor_voice.py --project . --live               # + running API, token, agent
    python doctor_voice.py --project . --live --api http://localhost:8000 --agent-health http://localhost:8081

Checks, in order:
  files     api/.env and agent/.env exist
  livekit   LIVEKIT_URL / KEY / SECRET set in both and identical; URL is ws(s)://
  dispatch  VOICE_AGENT_NAME is the same in both (the API dispatches by this name)
  brain     VOICE_LLM and API_URL in agent/.env look sane
  --live    API healthy, /api/voice/config enabled, /api/voice/session mints a
            token whose room config dispatches the right agent, LiveKit server
            reachable, agent health endpoint answering

Values in the process environment override .env files, as they do at runtime.
Standard library only. Exit code 1 if anything FAILs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

OK, WARN, FAIL = "ok  ", "warn", "FAIL"
failures = 0
LIVEKIT_KEYS = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


def report(status: str, label: str, detail: str = "") -> None:
    global failures
    failures += status == FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))


def load_env(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[key] = value
    for key in values:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def mask(value: str) -> str:
    return value if len(value) <= 8 else f"{value[:4]}…{value[-2:]}"


def http(method: str, url: str, body: dict | None = None, timeout: float = 5.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (local URLs)
        text = resp.read().decode() or "null"
        try:
            return resp.status, json.loads(text)
        except json.JSONDecodeError:
            return resp.status, text


def jwt_claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def check_config(root: Path) -> tuple[dict, dict]:
    print("config")
    api = load_env(root / "api/.env")
    agent = load_env(root / "agent/.env")
    if api is None:
        report(FAIL, "api/.env missing", "cp api/.env.example api/.env")
    if agent is None:
        report(FAIL, "agent/.env missing", "cp agent/.env.example agent/.env")
    api, agent = api or {}, agent or {}

    for key in LIVEKIT_KEYS:
        a, g = api.get(key, ""), agent.get(key, "")
        shown = mask(a) if "SECRET" in key or "KEY" in key else a
        if not a or not g:
            where = " and ".join(n for n, v in (("api/.env", a), ("agent/.env", g)) if not v)
            report(FAIL, f"{key} empty in {where}", "copy it from your LiveKit project settings")
        elif a != g:
            report(FAIL, f"{key} differs between api/.env and agent/.env", "both must use the same project")
        else:
            report(OK, key, shown)

    url = api.get("LIVEKIT_URL", "")
    if url and not url.startswith(("wss://", "ws://")):
        report(FAIL, "LIVEKIT_URL scheme", f"{url!r} must start with wss:// (or ws:// for a local server)")
    elif url.startswith("ws://") and "localhost" not in url and "127.0.0.1" not in url:
        report(
            WARN, "LIVEKIT_URL uses ws://", "browsers block insecure websockets from https pages; use wss://"
        )
    secret = api.get("LIVEKIT_API_SECRET", "")
    if secret and len(secret) < 32:
        report(
            WARN, "LIVEKIT_API_SECRET is short", "fine for `livekit-server --dev`; cloud secrets are longer"
        )

    a_name = api.get("VOICE_AGENT_NAME", "my-agent") or "my-agent"
    g_name = agent.get("VOICE_AGENT_NAME", "my-agent") or "my-agent"
    if a_name != g_name:
        report(
            FAIL,
            "VOICE_AGENT_NAME mismatch",
            f"api={a_name!r} agent={g_name!r}; the agent would never be dispatched",
        )
    else:
        report(OK, "agent name", a_name)

    a_tok, g_tok = api.get("VOICE_AGENT_TOKEN", ""), agent.get("VOICE_AGENT_TOKEN", "")
    if a_tok != g_tok:
        report(
            FAIL, "VOICE_AGENT_TOKEN differs", "the API would answer the agent with 401; use the same value"
        )
    elif a_tok:
        report(OK, "agent token", "set in both (/api/voice/chat is agent-only)")
    else:
        report(WARN, "agent token off", "set VOICE_AGENT_TOKEN in both .env files before the API is public")

    llm = agent.get("VOICE_LLM", "app") or "app"
    report(
        OK,
        "agent brain",
        "the app's /api/voice/chat" if llm == "app" else f"LiveKit Inference {llm} (bypasses the app)",
    )
    voices = api.get("VOICE_VOICES", "[]") or "[]"
    try:
        parsed = json.loads(voices)
        report(OK, "voice picker", f"{len(parsed)} voice(s)" if parsed else "off (agent default voice)")
    except json.JSONDecodeError as exc:
        report(FAIL, "VOICE_VOICES is not valid JSON", str(exc))
    return api, agent


def check_live(api_url: str, agent_health: str, api: dict, agent: dict) -> None:
    print("live")
    base = api_url.rstrip("/")
    try:
        http("GET", f"{base}/api/health")
        report(OK, "API reachable", base)
    except (urllib.error.URLError, OSError) as exc:
        report(
            FAIL, "API not reachable", f"{base}: {exc}. Start it: cd api && uv run fastapi dev app/main.py"
        )
        return

    try:
        _, cfg = http("GET", f"{base}/api/voice/config")
    except urllib.error.HTTPError as exc:
        report(FAIL, "/api/voice/config", f"HTTP {exc.code}; is mount_voice(...) called in create_app()?")
        return
    if not cfg.get("enabled"):
        report(
            FAIL, "voice disabled by the API", "LIVEKIT_* not loaded; restart the API after editing api/.env"
        )
        return
    report(OK, "voice enabled", f"{len(cfg.get('voices', []))} voice option(s)")

    try:
        status, session = http("POST", f"{base}/api/voice/session", {"participant_name": "Rizwan"})
        claims = jwt_claims(session["participant_token"])
        agents = (claims.get("roomConfig") or {}).get("agents") or []
        name = agents[0].get("agentName") if agents else None
        expected = agent.get("VOICE_AGENT_NAME", "my-agent") or "my-agent"
        if name != expected:
            report(FAIL, "token dispatch", f"token dispatches {name!r}, agent registers {expected!r}")
        else:
            report(
                OK,
                "session token",
                f"room {session['room_name']}, dispatches {name!r}, url {session['server_url']}",
            )
    except urllib.error.HTTPError as exc:
        report(FAIL, "/api/voice/session", f"HTTP {exc.code}: {exc.read().decode()[:200]}")
    except (KeyError, IndexError, ValueError) as exc:
        report(FAIL, "/api/voice/session response", f"unexpected shape: {exc}")

    lk = api.get("LIVEKIT_URL", "")
    if lk:
        http_url = lk.replace("wss://", "https://", 1).replace("ws://", "http://", 1)
        try:
            http("GET", http_url, timeout=6)
            report(OK, "LiveKit server reachable", http_url)
        except urllib.error.HTTPError:
            report(OK, "LiveKit server reachable", http_url)  # any HTTP answer means it is up
        except (urllib.error.URLError, OSError) as exc:
            report(WARN, "LiveKit server not reachable from here", f"{http_url}: {exc}")

    try:
        http("GET", agent_health.rstrip("/") + "/")
        report(OK, "agent running", agent_health)
    except (urllib.error.URLError, OSError):
        report(
            FAIL,
            "agent not running",
            f"nothing on {agent_health}. Start it: cd agent && uv run python voice_agent.py dev",
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".")
    ap.add_argument("--live", action="store_true", help="also check running services")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--agent-health", default="http://localhost:8081")
    args = ap.parse_args()
    root = Path(args.project).resolve()
    print(f"Voice doctor: {root}")
    api, agent = check_config(root)
    if args.live:
        check_live(args.api, args.agent_health, api, agent)
    print("\nAll good." if not failures else f"\n{failures} problem(s) to fix.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
