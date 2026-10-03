"""Download model files ahead of time (for Docker images and offline servers).

    uv run python -m app.download                 # every enabled model
    uv run python -m app.download --model ProsusAI/finbert

Only the files the API needs are fetched: config, tokenizer and model.safetensors
(never the pickled .bin, TensorFlow or Flax weights). Afterwards the API can run
with HF_HUB_OFFLINE=1.
"""

import argparse
import sys

from huggingface_hub import snapshot_download

from app.core.config import get_settings
from app.ml.catalog import CATALOG

ALLOW_PATTERNS = [
    "config.json",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
    "vocab.json",
    "merges.txt",
]


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--model",
        action="append",
        choices=list(CATALOG),
        help="Model id to download (repeatable). Default: every enabled model.",
    )
    args = parser.parse_args(argv)
    model_ids = args.model or settings.enabled_models

    failed = 0
    for model_id in model_ids:
        spec = CATALOG[model_id]
        print(f"→ {spec.name}  {spec.id}@{spec.revision}", flush=True)
        try:
            path = snapshot_download(
                spec.id,
                revision=spec.revision,
                allow_patterns=ALLOW_PATTERNS,
                cache_dir=settings.model_cache_dir,
            )
        except Exception as exc:
            failed += 1
            print(f"  ✗ {exc}", file=sys.stderr, flush=True)
        else:
            print(f"  ✓ {path}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
