"""Render references/manual-edits.md from scripts/patches.py and scripts/patches_no_voice.py.

    python scripts/maintain/render_manual_edits.py
"""

import difflib
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from patches import EDITS  # noqa: E402
from patches_no_voice import EDITS as EDITS_NO_VOICE  # noqa: E402

out = [
    "# Manual edits",
    "",
    "Every edit `install_photos.py` makes to existing files, numbered the way its",
    "report numbers them. Use this when the installer says a file was customised:",
    "find the variant, file and edit number, then make the `+` lines appear where",
    "the unchanged (space-prefixed) lines point. Lines starting with `-` are",
    "replaced. Generated from `scripts/patches*.py`; do not edit by hand.",
    "",
    "The installer reports which variant it matched: **with voice mode** (the",
    "template after the livekit-voice-mode skill, and every template since) or",
    "**without voice mode**. The API edits are the same in both.",
    "",
    "What each file gets, in one line:",
    "",
    "| File | Change |",
    "|---|---|",
    "| `api/app/core/config.py` | `max_images_per_message/_request`, `max_image_bytes`, `vision_models` |",
    "| `api/app/main.py` | `BodySizeLimit` on `/api/chat`; registry gets `vision_models` |",
    "| `api/app/schemas.py` | `ImageInput` (decode + sniff), `ChatMessage.images`, `ModelInfo.vision`, `default_vision`, `ImageLimits`, image count before decoding |",
    "| `api/app/providers/ollama.py` | `to_ollama_messages` (bytes), capabilities via `show` (cached by digest), embeddings filter |",
    "| `api/app/providers/anthropic.py` | `to_anthropic_turn` (image blocks), 5 MB guard, `vision` flag |",
    "| `api/app/providers/openai_compat.py` | `to_openai_message` (`image_url` parts), `vision` flag |",
    "| `api/app/providers/registry.py` | `vision_patterns`, `default_vision`, `model_info`, `vision_check`, vision-only candidates |",
    "| `api/app/services/chat.py` | vision routing, `text_only_message`, `NO_VISION_MESSAGE` |",
    "| `api/app/routes/chat.py` | per-message / per-request / size limits (422) |",
    "| `api/app/routes/models.py` | `image_limits` in the response |",
    "| `api/tests/conftest.py`, `test_models.py` | `FakeProvider(vision_models=…)`, registry patterns, `vision` in expectations |",
    "| `web/lib/types.ts` | `ChatImage`, `ImageLimits`, `ModelInfo.vision`, `default_vision`, `ChatMessage.images` |",
    "| `web/lib/api.ts` | `ApiMessage` with `images`; strip Pydantic's `Value error, ` |",
    "| `web/hooks/use-chat.ts` | `ImagePolicy`, `toApiMessages`, `send(text, images)`, photo titles, cleanup at load |",
    "| `web/components/chat/composer.tsx` | + menu, file/camera inputs, tray, notice slot, count, send rules |",
    "| `web/components/chat/message*.tsx` | gallery, photo-only messages, \"Looking at N photos…\" |",
    "| `web/components/chat/model-picker.tsx` | \"Sees images\" tags; Auto label shows the vision model |",
    "| `web/components/chat/app-sidebar.tsx` | photo icon on chats with photos |",
    "| `web/components/chat/chat-app.tsx` | attachments, vision notice, privacy line, drop/paste zone, suggestions with photos |",
    "",
]


def section(title: str, edits) -> None:
    files: dict[str, list[tuple[str, str]]] = {}
    for f, old, new in edits:
        files.setdefault(f, []).append((old, new))
    out.append(f"# {title}")
    out.append("")
    out.append("Files: " + ", ".join(f"`{f}` ({len(e)})" for f, e in files.items()))
    out.append("")
    for f, file_edits in files.items():
        out.append(f"## {f}")
        out.append("")
        for i, (old, new) in enumerate(file_edits, 1):
            diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=50)
            body = [ln for ln in diff if not ln.startswith(("---", "+++", "@@"))]
            out.append(f"**Edit {i} of {len(file_edits)}**")
            out.append("")
            out.append("```diff")
            out.extend(body)
            out.append("```")
            out.append("")


section("With voice mode", EDITS)
section("Without voice mode", EDITS_NO_VOICE)
(SKILL / "references" / "manual-edits.md").write_text("\n".join(out))
print("wrote references/manual-edits.md")
