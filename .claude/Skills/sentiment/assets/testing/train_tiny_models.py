"""Train tiny stand-ins for the four catalog models (no downloads).

Same architecture, tokenizer type and label order as the real checkpoints, a few
thousand parameters, trained for seconds on a synthetic sentiment set so outputs
react to the text. For running the app end to end where Hugging Face is out of
reach (CI, sandboxes). Scores are meaningless; the mechanics are real.

    cd api && uv run python <skill>/assets/testing/train_tiny_models.py <out-dir>

Then point the API at them (api/.env):
    MODEL_SOURCES={"ProsusAI/finbert":"<out>/finbert", ...}   # printed at the end
"""

import json
import random
import shutil
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path.cwd()))  # the project's api/ folder
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from app.ml.catalog import DISTILBERT_SST2, FINBERT, MULTILINGUAL_STARS, TWITTER_ROBERTA  # noqa: E402
from tests import conftest as builders  # noqa: E402

POS = "good great excellent love amazing happy best fast friendly clean helpful profit growth".split()
NEG = "bad terrible awful hate worst slow rude broken dirty poor refund loss".split()
NOUN = (
    "service food room staff battery life delivery price quality support product app camera "
    "wifi breakfast movie hotel phone company shares earnings"
).split()


def sentence(polarity: int) -> str:
    noun = random.choice(NOUN)
    if polarity == 0:
        return f"the {noun} was {random.choice(['there', 'the', 'it'])}"
    word = random.choice(POS if polarity > 0 else NEG)
    boost = random.choice(["", "very ", "really "])
    if random.random() < 0.25:
        return f"the {noun} was not {random.choice(NEG if polarity > 0 else POS)}"
    if random.random() < 0.3:
        other = random.choice(NEG if polarity > 0 else POS)
        return f"the {noun} was {other} but the {random.choice(NOUN)} was {boost}{word}"
    return f"the {noun} was {boost}{word}"


def train(path: Path, target_of) -> None:
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path)
    head = model.classifier if hasattr(model.classifier, "bias") else model.classifier.out_proj
    torch.nn.init.zeros_(head.bias)
    data = [(sentence(p), p) for p in [-1, 0, 1] * 400]
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3)
    model.train()
    for _ in range(6):
        random.shuffle(data)
        for i in range(0, len(data), 32):
            batch = data[i : i + 32]
            enc = tokenizer([t for t, _ in batch], padding=True, return_tensors="pt")
            loss = model(**enc, labels=torch.tensor([target_of(p) for _, p in batch])).loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    model.eval()
    tokenizer.save_pretrained(path)
    model.save_pretrained(path, safe_serialization=True)


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    shutil.rmtree(out, ignore_errors=True)
    tmp = out / "_build"
    tmp.mkdir(parents=True)
    random.seed(0)
    torch.manual_seed(0)
    plans = [
        (FINBERT, "finbert", lambda: builders.build_bert(tmp, FINBERT.labels, 0), {1: 0, -1: 1, 0: 2}),
        (DISTILBERT_SST2, "distilbert", lambda: builders.build_distilbert(tmp, 0), {1: 1, -1: 0, 0: 0}),
        (TWITTER_ROBERTA, "roberta", lambda: builders.build_roberta(tmp, 0), {-1: 0, 0: 1, 1: 2}),
        (MULTILINGUAL_STARS, "stars", lambda: builders.build_bert(tmp, MULTILINGUAL_STARS.labels, 0), {-1: 0, 0: 2, 1: 4}),
    ]
    sources = {}
    for spec, folder, build, mapping in plans:
        path = build()
        train(path, mapping.__getitem__)
        shutil.move(path, out / folder)
        sources[spec.id] = str(out / folder)
        print(f"✓ {spec.name} → {out / folder}", flush=True)
    shutil.rmtree(tmp)
    print("\nAdd to api/.env:\nMODEL_SOURCES=" + json.dumps(sources))


if __name__ == "__main__":
    main()
