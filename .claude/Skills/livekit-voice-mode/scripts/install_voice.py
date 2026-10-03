#!/usr/bin/env python3
"""Install LiveKit voice mode into a fullstack-ai-assistant project.

    python install_voice.py --project path/to/app            # install
    python install_voice.py --project path/to/app --dry-run  # show what would change
    python install_voice.py --project path/to/app --no-install

The project layout this targets (the fullstack-ai-assistant template):

    api/   FastAPI app with app/main.py:create_app() and a ChatService
    web/   Next.js app with components/chat/chat-app.tsx
    agent/ (created) LiveKit Agents worker

What it does, in order. Every step is safe to re-run:

1. Copies self-contained files: agent/, api/app/voice/, api/app/voice_brain.py,
   api/tests/test_voice.py, web/lib/voice.ts, web/hooks/use-voice-config.ts,
   web/components/voice/. A file that already exists with different content is
   left alone (reported) unless --force is given.
2. Adds dependencies: livekit-api to api/pyproject.toml; livekit-client and
   @livekit/components-react to web/package.json. Then runs `uv sync` in api/
   and agent/ and `npm install` in web/ unless --no-install.
3. Applies anchored edits to the files that wire voice into the app (see
   patches.py). An edit whose result is already present is skipped. An edit
   whose anchor is missing (the file was customised) leaves that whole file
   unchanged (or, with --partial, applies the rest) and is reported as a manual
   step pointing at references/manual-edits.md, which lists every edit by number.
4. Adds the voice block to api/.env.example (and to api/.env when it exists and
   has no LIVEKIT_URL yet), creates agent/.env from its example, and adds a
   voice section to the root README.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
sys.path.insert(0, str(HERE))

from patches import EDITS  # noqa: E402

TEMPLATE_AGENT_NAME = "ai-assistant-agent"
API_DEPS = ['"livekit-api>=1.2.1"']
WEB_DEPS = {"@livekit/components-react": "^2.9.24", "livekit-client": "^2.22.3"}

COPY = [
    # (asset path, project path, part)
    ("agent", "agent", "agent"),
    ("api/app/voice", "api/app/voice", "api"),
    ("api/app/voice_brain.py", "api/app/voice_brain.py", "api"),
    ("api/tests/test_voice.py", "api/tests/test_voice.py", "api"),
    ("web/lib/voice.ts", "web/lib/voice.ts", "web"),
    ("web/hooks/use-voice-config.ts", "web/hooks/use-voice-config.ts", "web"),
    ("web/components/voice", "web/components/voice", "web"),
]
SKIP_NAMES = {".venv", "__pycache__", ".ruff_cache", ".pytest_cache", ".env", "node_modules"}

# Where each wired file is explained, for manual steps.
GUIDE = {
    "api/app/main.py": "references/integrate-fastapi.md",
    "api/.env.example": "references/configuration.md",
    "docker-compose.yml": "references/deployment.md",
}
WEB_GUIDE = "references/integrate-nextjs.md"

ENV_BLOCK = """
# ---------- Voice mode (LiveKit) ----------
# Voice is enabled when all three are set. Use the same project as the agent.
# LIVEKIT_URL must be reachable from the browser (e.g. wss://<project>.livekit.cloud).
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
# Must match VOICE_AGENT_NAME in agent/.env
VOICE_AGENT_NAME=my-agent
# Shared secret the agent sends to /api/voice/chat (same value in agent/.env). Empty = off.
# Set it whenever the API is reachable from the internet:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
VOICE_AGENT_TOKEN=
# Optional voice picker (ids passed to the agent's TTS). Leave [] to use the agent default.
# VOICE_VOICES=[{"id":"calm","name":"Calm","description":"Even and relaxed","tts_voice":"<tts voice id>"}]
VOICE_VOICES=[]
"""

README_SECTION = """## Voice mode (LiveKit)

Voice mode appears as a sound-wave button in the empty message box once the
API has LiveKit credentials. It needs a [LiveKit Cloud](https://cloud.livekit.io)
project, because speech-to-text, text-to-speech, turn detection and noise
cancellation run on LiveKit Inference.

```bash
# api/.env and agent/.env: the same three values from your LiveKit project
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

# Voice agent (new terminal; API must be running)
cd agent
uv sync
uv run python voice_agent.py dev
```

With Docker: fill in agent/.env, then `docker compose --profile voice up --build`.

How a session flows:

```
Browser ──POST /api/voice/session──► API: new room + token that dispatches the agent
   │                                     (remembers the chosen model and earlier chat)
   └──WebRTC (mic + speaker)──► LiveKit ◄── agent: STT → turn detection → reply → TTS
                                                │
                                   POST /api/voice/chat  (same model dropdown,
                                   Ollama first, cloud fallback as text chat)
```

- Replies use the model picked in the dropdown, with the same fallback as
  text chat. The agent shows which model answered.
- Talking over the assistant interrupts it; **Stop** and **Esc** do too.
- Transcripts are saved into the chat (tagged *Spoken*), so a voice
  conversation can continue by typing and vice versa.
- If a model fails the assistant says so out loud and the UI shows the
  reason; if the agent is not running the UI says so after 20 seconds.
- Anyone who can reach `/api/voice/session` can start a (billed) voice
  session, so put it behind your login before going public, and set the same
  `VOICE_AGENT_TOKEN` in api/.env and agent/.env so only the agent can call
  `/api/voice/chat`.

Voice settings (agent/.env): `VOICE_STT_MODEL`, `VOICE_STT_LANGUAGE`,
`VOICE_TTS_MODEL`, `VOICE_TTS_VOICE`, `VOICE_GREETING`, `VOICE_INSTRUCTIONS`,
`VOICE_NOISE_CANCELLATION`, and `VOICE_LLM` (`app`, or a LiveKit Inference model
id to bypass the app). Offer a voice picker with `VOICE_VOICES` in api/.env.

"""


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
        "api": main.exists() and "def create_app" in read(main),
        "web": (root / "web/components/chat/chat-app.tsx").exists(),
    }


# ---------------------------------------------------------------- step 1: copy
def iter_files(src: Path):
    if src.is_file():
        yield src, Path()
        return
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if path.is_file() and not SKIP_NAMES.intersection(rel.parts):
            yield path, rel


def copy_assets(root: Path, parts: set[str], rep: Report, dry: bool, force: bool, slug: str | None):
    for asset, target, part in COPY:
        if part not in parts:
            continue
        src, dest_root = ASSETS / asset, root / target
        added = changed = kept = 0
        for path, rel in iter_files(src):
            dest = dest_root / rel if rel.parts else dest_root
            data = path.read_bytes()
            if slug and part == "agent" and rel.name in {"pyproject.toml", "uv.lock"}:
                data = data.replace(
                    f'name = "{TEMPLATE_AGENT_NAME}"'.encode(), f'name = "{slug}-agent"'.encode()
                )
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
                shutil.copymode(path, dest)
        if added or changed:
            rep.done.append(f"copied {target} ({added} new, {changed} replaced)")
        elif not kept:
            rep.same.append(f"{target} already present")


# ---------------------------------------------------------------- step 2: deps
def add_api_dep(root: Path, rep: Report, dry: bool) -> bool:
    path = root / "api/pyproject.toml"
    text = read(path)
    if "livekit-api" in text:
        rep.same.append("api dependency livekit-api already present")
        return False
    match = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    if not match:
        rep.manual.append('api/pyproject.toml: add "livekit-api>=1.2.1" to [project].dependencies')
        return False
    body = match.group(1)
    indent = re.search(r"\n(\s+)\"", body)
    pad = indent.group(1) if indent else "    "
    new_body = body.rstrip() + ("" if body.rstrip().endswith(",") or not body.strip() else ",")
    new_body += "".join(f"\n{pad}{dep}," for dep in API_DEPS) + "\n"
    text = text[: match.start(1)] + new_body + text[match.end(1) :]
    write(path, text, dry)
    rep.done.append("added livekit-api to api/pyproject.toml")
    return True


def add_web_deps(root: Path, rep: Report, dry: bool) -> bool:
    path = root / "web/package.json"
    pkg = json.loads(read(path))
    deps = pkg.setdefault("dependencies", {})
    missing = {k: v for k, v in WEB_DEPS.items() if k not in deps}
    if not missing:
        rep.same.append("web dependencies already present")
        return False
    deps.update(missing)
    pkg["dependencies"] = dict(sorted(deps.items()))
    write(path, json.dumps(pkg, indent=2, ensure_ascii=False) + "\n", dry)
    rep.done.append(f"added {', '.join(missing)} to web/package.json")
    return True


def run(cmd: list[str], cwd: Path, rep: Report, label: str) -> None:
    if not shutil.which(cmd[0]):
        rep.manual.append(f"{label}: `{cmd[0]}` not found; run `{' '.join(cmd)}` in {cwd.name}/")
        return
    print(f"  $ (cd {cwd.name} && {' '.join(cmd)})")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=sys.platform == "win32")
    if result.returncode:
        rep.manual.append(
            f"{label} failed; run `{' '.join(cmd)}` in {cwd.name}/\n      {result.stderr.strip()[-400:]}"
        )
    else:
        rep.done.append(label)


# ---------------------------------------------------------------- step 3: wiring edits
def apply_edits(root: Path, parts: set[str], rep: Report, dry: bool, partial: bool) -> None:
    by_file: dict[str, list[tuple[str, str]]] = {}
    for file, old, new in EDITS:
        by_file.setdefault(file, []).append((old, new))
    for file, edits in by_file.items():
        part = file.split("/", 1)[0]
        if part == "docker-compose.yml":
            part = "agent"
        if part not in parts:
            continue
        path = root / file
        guide = GUIDE.get(file, WEB_GUIDE)
        if not path.exists():
            rep.manual.append(f"{file}: file not found; see {guide}")
            continue
        text = read(path)
        applied, present, failed = 0, 0, []
        for i, (old, new) in enumerate(edits, 1):
            if new in text:
                present += 1
            elif text.count(old) == 1:
                text = text.replace(old, new)
                applied += 1
            else:
                failed.append(str(i))
        where = f"references/manual-edits.md ({file}, edit {', '.join(failed)} of {len(edits)}) and {guide}"
        if failed and not partial:
            # A half-wired file may not compile, so leave it exactly as it was.
            rep.manual.append(f"{file}: customised, left unchanged. Apply by hand: {where}")
            continue
        if applied:
            write(path, text, dry)
            rep.done.append(f"wired {file} ({applied} edit{'s' * (applied > 1)})")
        elif present == len(edits):
            rep.same.append(f"{file} already wired")
        if failed:
            rep.manual.append(f"{file}: partly wired. Finish by hand: {where}")


# ---------------------------------------------------------------- step 4: env + docs
def env_and_docs(root: Path, parts: set[str], rep: Report, dry: bool) -> None:
    if "api" in parts:
        env = root / "api/.env"
        if env.exists() and "LIVEKIT_URL" not in read(env):
            write(env, read(env).rstrip("\n") + "\n" + ENV_BLOCK, dry)
            rep.done.append("added empty LIVEKIT_* settings to api/.env (fill them in)")
    if "agent" in parts:
        env, example = root / "agent/.env", root / "agent/.env.example"
        if not env.exists() and (example.exists() or dry):
            if not dry:
                shutil.copyfile(example, env)
            rep.done.append("created agent/.env from agent/.env.example (fill in LIVEKIT_*)")
    readme = root / "README.md"
    if readme.exists():
        text = read(readme)
        if "## Voice mode" in text:
            rep.same.append("README voice section already present")
        else:
            anchor = "## How model selection works"
            if anchor in text:
                text = text.replace(anchor, README_SECTION + anchor, 1)
            else:
                text = text.rstrip("\n") + "\n\n" + README_SECTION.rstrip("\n") + "\n"
            write(readme, text, dry)
            rep.done.append("added a Voice mode section to README.md")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=".", help="project root containing api/ and web/")
    ap.add_argument("--dry-run", action="store_true", help="report changes without writing")
    ap.add_argument("--no-install", action="store_true", help="skip `uv sync` and `npm install`")
    ap.add_argument("--force", action="store_true", help="replace copied files that you changed")
    ap.add_argument(
        "--partial",
        action="store_true",
        help="apply the edits that match even when others in the same file do not",
    )
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=["api", "web", "agent"],
        help="leave a part out (repeatable)",
    )
    args = ap.parse_args()

    root = Path(args.project).resolve()
    found = detect(root)
    if not any(found.values()):
        print(f"No fullstack-ai-assistant layout found in {root}.")
        print("Expected api/app/main.py with create_app() and/or web/components/chat/chat-app.tsx.")
        print("For another stack, follow references/integrate-fastapi.md and references/integrate-nextjs.md.")
        return 2

    parts = {p for p, ok in found.items() if ok} | {"agent"}
    parts -= set(args.skip)
    for p, ok in found.items():
        if not ok and p not in args.skip:
            print(f"note: {p}/ not found or not the template layout; skipping it")

    slug = None
    if "api" in found and found["api"]:
        m = re.search(r'^name\s*=\s*"(.+?)-api"', read(root / "api/pyproject.toml"), re.M)
        slug = m.group(1) if m else None

    rep = Report()
    print(f"Installing voice mode into {root}{'  (dry run)' if args.dry_run else ''}")
    copy_assets(root, parts, rep, args.dry_run, args.force, slug)
    api_changed = "api" in parts and add_api_dep(root, rep, args.dry_run)
    web_changed = "web" in parts and add_web_deps(root, rep, args.dry_run)
    apply_edits(root, parts, rep, args.dry_run, args.partial)
    env_and_docs(root, parts, rep, args.dry_run)

    if not args.dry_run and not args.no_install:
        # `uv sync` (not just `uv lock`): an existing api/.venv must get livekit-api now,
        # or `.venv/bin/uvicorn` and IDEs fail with "No module named 'livekit'".
        if "api" in parts:
            run(["uv", "sync"], root / "api", rep, "installed api dependencies (uv sync)")
        if "agent" in parts:
            run(["uv", "sync"], root / "agent", rep, "installed agent dependencies (uv sync)")
        if web_changed:
            run(
                ["npm", "install", "--no-audit", "--no-fund"],
                root / "web",
                rep,
                "installed web dependencies (npm install)",
            )
    elif args.no_install and (api_changed or web_changed):
        rep.notes.append(
            "dependencies were added but not installed: run `uv sync` in api/ and agent/, `npm install` in web/"
        )

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
        "  1. Put the same LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET in api/.env and agent/.env\n"
        "  2. cd agent && uv run python voice_agent.py download-files\n"
        "  3. Run api, web, then:  cd agent && uv run python voice_agent.py dev\n"
        "  4. Check the setup:     python <skill>/scripts/doctor_voice.py --project .\n"
    )
    return 1 if rep.manual else 0


if __name__ == "__main__":
    raise SystemExit(main())
