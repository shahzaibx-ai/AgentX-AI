"""Render references/manual-edits.md from scripts/patches.py.

python scripts/maintain/render_manual_edits.py
"""

import difflib
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from patches import EDITS  # noqa: E402

LANG = {".py": "diff", ".ts": "diff", ".tsx": "diff", ".yml": "diff", ".example": "diff"}

out = [
    "# Manual edits",
    "",
    "Every edit `install_voice.py` makes to existing files, numbered the same way",
    "its report numbers them. Use this when the installer says a file was",
    "customised: find the file and edit number, then make the `+` lines appear in",
    "the place the unchanged (space-prefixed) lines point to. Lines starting with",
    "`-` are replaced. Generated from `scripts/patches.py`; do not edit by hand.",
    "",
]
files: dict[str, list[tuple[str, str]]] = {}
for f, old, new in EDITS:
    files.setdefault(f, []).append((old, new))
out.append("Files: " + ", ".join(f"`{f}` ({len(e)})" for f, e in files.items()))
out.append("")
for f, edits in files.items():
    out.append(f"## {f}")
    out.append("")
    for i, (old, new) in enumerate(edits, 1):
        diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=50)
        body = [ln for ln in diff if not ln.startswith(("---", "+++", "@@"))]
        out.append(f"**Edit {i} of {len(edits)}**")
        out.append("")
        out.append("```diff")
        out.extend(body)
        out.append("```")
        out.append("")
(SKILL / "references" / "manual-edits.md").write_text("\n".join(out))
print("wrote references/manual-edits.md")
