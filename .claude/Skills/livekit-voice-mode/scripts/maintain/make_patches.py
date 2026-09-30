"""Regenerate scripts/patches.py from a pre-voice and a voice version of the template.

    python scripts/maintain/make_patches.py <pre-voice-project> <voice-project> scripts/patches.py

For each wired file (FILES), diffs the two versions and emits the smallest
(old -> new) edits whose context makes them unique, then checks that applying
them in order reproduces the voice version exactly. Add a file to FILES when
voice starts touching it.
"""

import difflib
import sys
from pathlib import Path

BEFORE = Path(sys.argv[1])  # pre-voice project
AFTER = Path(sys.argv[2])  # voice project
OUT = Path(sys.argv[3])

FILES = [
    "api/app/main.py",
    "api/.env.example",
    "docker-compose.yml",
    "web/lib/types.ts",
    "web/hooks/use-chat.ts",
    "web/components/chat/composer.tsx",
    "web/components/chat/message.tsx",
    "web/components/chat/app-sidebar.tsx",
    "web/components/chat/chat-app.tsx",
]


def edits_for(before: str, after: str) -> list[tuple[str, str]]:
    a = before.splitlines(keepends=True)
    b = after.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    hunks = [op for op in sm.get_opcodes() if op[0] != "equal"]
    out = []
    for _, i1, i2, j1, j2 in hunks:
        # grow context until the old block is unique in before and new block unique in after
        for ctx in range(1, 12):
            lo, hi = max(0, i1 - ctx), min(len(a), i2 + ctx)
            blo, bhi = j1 - (i1 - lo), j2 + (hi - i2)
            old = "".join(a[lo:hi])
            new = "".join(b[blo:bhi])
            # skip context lines that are blank-only at the edges for robustness? keep simple
            if before.count(old) == 1 and after.count(new) == 1 and old.strip():
                break
        else:
            raise SystemExit(f"could not make unique hunk at {i1}")
        out.append((old, new))
    # verify: applying sequentially reproduces after
    text = before
    for old, new in out:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    assert text == after, "sequential application does not reproduce target"
    return out


def lit(s: str) -> str:
    if "'''" not in s and "\\" not in s and not s.endswith("'"):
        return "'''" + s + "'''"
    return repr(s)


lines = [
    '"""Anchored edits that wire voice mode into the fullstack-ai-assistant template.',
    "",
    "Generated from the verified pre-voice and voice versions of each file.",
    "Each edit replaces OLD (which must appear exactly once) with NEW. An edit whose",
    "NEW text is already present counts as applied, so the installer is idempotent.",
    '"""',
    "",
    "EDITS: list[tuple[str, str, str]] = [",
]
total = 0
for f in FILES:
    before = (BEFORE / f).read_text()
    after = (AFTER / f).read_text()
    for old, new in edits_for(before, after):
        lines.append(f"    # ---- {f}")
        lines.append(f"    (\n        {f!r},\n        {lit(old)},\n        {lit(new)},\n    ),")
        total += 1
lines.append("]")
OUT.write_text("\n".join(lines) + "\n")
print(f"{total} edits -> {OUT}")
