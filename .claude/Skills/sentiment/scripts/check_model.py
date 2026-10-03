#!/usr/bin/env python3
"""Check whether a Hugging Face model can be added to Sentiment Studio, and print its catalog entry.

Run with the project's environment (it needs huggingface_hub and internet access):

    cd api && uv run python <skill>/scripts/check_model.py siebert/sentiment-roberta-large-english

It checks:
  - safetensors weights exist (torch 2.2.2 cannot load pickled .bin safely): on `main`,
    or else on a Hugging Face conversion-bot ("SFconvertbot") pull request, whose
    revision is then pinned as `refs/pr/N`
  - it is a sequence-classification model and reads its labels (id2label)
  - a fast tokenizer can be built (needed for word offsets)
  - the architecture accepts `inputs_embeds` (needed for word-influence explanations)
and prints a ModelSpec to paste into api/app/ml/catalog.py (review the polarity values).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

# Architectures verified with integrated gradients (inputs_embeds + fast tokenizer offsets).
KNOWN_GOOD = {
    "bert",
    "distilbert",
    "roberta",
    "xlm-roberta",
    "camembert",
    "electra",
    "albert",
    "deberta",
    "deberta-v2",
    "mpnet",
}
BOT = "SFconvertbot"


@dataclass
class Candidate:
    revision: str
    files: list[str]


def has_safetensors(files: list[str]) -> bool:
    return "model.safetensors" in files or "model.safetensors.index.json" in files


def choose_revision(main_files: list[str], bot_prs: list[Candidate]) -> Candidate | None:
    """main if it has safetensors, else the newest bot PR that does."""
    if has_safetensors(main_files):
        return Candidate("main", main_files)
    for pr in sorted(bot_prs, key=lambda c: int(c.revision.rsplit("/", 1)[-1]), reverse=True):
        if has_safetensors(pr.files):
            return pr
    return None


def guess_polarity(labels: list[str]) -> list[float] | None:
    """-1..+1 per label from common names; None when the names don't say (e.g. LABEL_0)."""
    out: list[float] = []
    stars = [re.match(r"^\s*(\d+)\s*stars?\s*$", label, re.I) for label in labels]
    if all(stars):
        values = [int(m.group(1)) for m in stars if m]
        lo, hi = min(values), max(values)
        return [round(-1 + 2 * (v - lo) / (hi - lo), 3) if hi > lo else 0.0 for v in values]
    for label in labels:
        name = label.lower()
        if re.search(r"\b(neg|negative|bad)\b", name):
            out.append(-1.0)
        elif re.search(r"\b(neu|neutral|mixed)\b", name):
            out.append(0.0)
        elif re.search(r"\b(pos|positive|good)\b", name):
            out.append(1.0)
        else:
            return None
    return out


def tokenizer_note(files: list[str]) -> tuple[bool, str]:
    if "tokenizer.json" in files:
        return True, "tokenizer.json (fast)"
    if "vocab.txt" in files:
        return True, "WordPiece vocab.txt (converted to fast automatically)"
    if "vocab.json" in files and "merges.txt" in files:
        return True, "byte-level BPE vocab.json + merges.txt (converted to fast automatically)"
    if any(f.endswith(".model") for f in files):
        return (
            False,
            "SentencePiece .model only: add `sentencepiece` and `protobuf` with `uv add` to build a fast tokenizer",
        )
    return False, "no tokenizer files found"


def render_spec(
    model_id: str,
    revision: str,
    labels: list[str],
    polarity: list[float] | None,
    architecture: str,
    *,
    domain: str,
) -> str:
    const = re.sub(r"[^A-Z0-9]+", "_", model_id.split("/")[-1].upper()).strip("_")
    pol = polarity if polarity is not None else [0.0] * len(labels)
    lines = [
        f"{const} = ModelSpec(",
        f"    id={model_id!r},",
        f"    name={model_id.split('/')[-1]!r},  # a short display name",
        f"    domain={domain!r},",
        '    description="What kind of text it is for.",',
        '    languages="English",  # check the model card',
        '    parameters="?",  # check the model card',
        f"    architecture={architecture!r},",
        f"    labels={tuple(label.lower() for label in labels)!r},",
        f"    polarity={tuple(pol)!r},{'  # TODO: set -1 (negative) .. +1 (positive) per label' if polarity is None else ''}",
    ]
    if revision != "main":
        lines.append(f"    revision={revision!r},  # safetensors conversion of main")
    lines.append(")")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_id")
    ap.add_argument("--domain", default="General")
    args = ap.parse_args(argv)

    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError:
        print(
            "Run this with the project's environment: cd api && uv run python .../check_model.py",
            file=sys.stderr,
        )
        return 2

    api = HfApi()
    model_id = args.model_id
    main_files = api.list_repo_files(model_id)
    prs: list[Candidate] = []
    if not has_safetensors(main_files):
        for d in api.get_repo_discussions(model_id, author=BOT, discussion_type="pull_request"):
            revision = f"refs/pr/{d.num}"
            prs.append(Candidate(revision, api.list_repo_files(model_id, revision=revision)))
    chosen = choose_revision(main_files, prs)
    problems = 0

    print(f"{model_id}")
    if chosen is None:
        print("  ✗ no safetensors weights on main or on a conversion-bot PR.")
        print("    torch 2.2.2 can't load its .bin weights safely. Options: pick another model,")
        print("    convert the weights yourself and serve them from a folder (MODEL_SOURCES), or")
        print("    upgrade torch to >= 2.6 (outside this project's pinned stack).")
        return 1
    print(f"  ✓ safetensors at revision {chosen.revision}")

    config = json.loads(open(hf_hub_download(model_id, "config.json", revision=chosen.revision)).read())
    architecture = (config.get("architectures") or ["?"])[0]
    model_type = config.get("model_type", "?")
    id2label = config.get("id2label") or {}
    labels = [str(id2label[k]) for k in sorted(id2label, key=int)]

    if not architecture.endswith("ForSequenceClassification"):
        problems += 1
        print(f"  ✗ architecture {architecture}: not a sequence-classification model")
    else:
        print(f"  ✓ {architecture} ({model_type}), {len(labels)} labels: {labels}")
    if model_type not in KNOWN_GOOD:
        print(
            f"  ! {model_type}: explanations untested for this architecture; run the test suite with a tiny version"
        )

    fast, note = tokenizer_note(chosen.files)
    print(f"  {'✓' if fast else '!'} tokenizer: {note}")
    problems += 0 if fast else 1

    polarity = guess_polarity(labels)
    if polarity is None:
        print(
            "  ! label names don't reveal sentiment (e.g. LABEL_0): read the model card and set labels/polarity"
        )
    positions = config.get("max_position_embeddings")
    if positions:
        print(f"  ✓ max_position_embeddings {positions}")

    print("\nAdd to api/app/ml/catalog.py and to CATALOG:\n")
    print(render_spec(model_id, chosen.revision, labels, polarity, architecture, domain=args.domain))
    print("\nThen: add a tiny checkpoint of this architecture to tests if it's new, run `uv run pytest`,")
    print("and add example texts for its domain in web/lib/config.ts (EXAMPLES).")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
