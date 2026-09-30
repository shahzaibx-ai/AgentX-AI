"""A loaded sentiment model: tokenizer + PyTorch model on one device."""

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)

from app.ml.catalog import ModelSpec
from app.ml.explain import integrated_gradients, word_attributions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LabelScore:
    label: str
    score: float
    logit: float


@dataclass(frozen=True)
class Attribution:
    text: str
    weight: float


@dataclass(frozen=True)
class Prediction:
    label: str
    score: float
    probs: list[LabelScore]
    """All classes, ordered from most negative to most positive."""
    tokens: list[str]
    num_tokens: int
    """Tokens in the full text (including special tokens), before truncation."""
    truncated: bool
    attributions: list[Attribution] | None = None


class SentimentClassifier:
    def __init__(
        self,
        spec: ModelSpec,
        model: PreTrainedModel,
        tokenizer: PreTrainedTokenizerBase,
        *,
        device: torch.device,
        max_length: int = 512,
        batch_size: int = 32,
    ) -> None:
        num_labels = model.config.num_labels
        if num_labels != len(spec.labels):
            raise ValueError(
                f"{spec.id}: the checkpoint has {num_labels} labels, the catalog lists "
                f"{len(spec.labels)}"
            )
        _warn_on_label_mismatch(spec, model)
        if not tokenizer.is_fast:
            raise ValueError(f"{spec.id}: a fast tokenizer is required (for word offsets)")

        self.spec = spec
        self.model = model.to(device).eval()
        for param in self.model.parameters():
            param.requires_grad_(False)
        self.tokenizer = tokenizer
        self.device = device
        positions = getattr(model.config, "max_position_embeddings", max_length)
        # RoBERTa reserves 2 positions for its padding offset.
        limit = (
            positions - 2 if model.config.model_type in ("roberta", "xlm-roberta") else positions
        )
        self.max_length = min(max_length, limit)
        self.batch_size = batch_size
        self._lock = threading.Lock()  # one forward pass at a time per model
        self._polarity = torch.tensor(spec.polarity, dtype=torch.float32)

    @classmethod
    def load(
        cls,
        spec: ModelSpec,
        *,
        source: str | Path | None = None,
        device: torch.device,
        max_length: int = 512,
        batch_size: int = 32,
        cache_dir: str | None = None,
    ) -> "SentimentClassifier":
        """Load from the Hub (at the catalog's pinned revision) or a local folder.

        Only safetensors weights are accepted; pickled `.bin` files are never loaded.
        """
        location = str(source or spec.id)
        is_local = Path(location).is_dir()
        revision = None if is_local else spec.revision
        logger.info("loading %s from %s%s", spec.id, location, f"@{revision}" if revision else "")
        tokenizer = AutoTokenizer.from_pretrained(
            location, revision=revision, cache_dir=cache_dir, use_fast=True
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            location, revision=revision, cache_dir=cache_dir, use_safetensors=True
        )
        return cls(
            spec, model, tokenizer, device=device, max_length=max_length, batch_size=batch_size
        )

    def predict(
        self, texts: Sequence[str], *, explain: bool = False, explain_steps: int = 16
    ) -> list[Prediction]:
        prepared = [self.spec.prepare(t) for t in texts]
        order = self.spec.display_order
        results: list[Prediction] = []
        with self._lock:
            for start in range(0, len(prepared), self.batch_size):
                chunk = prepared[start : start + self.batch_size]
                full = self.tokenizer(chunk, truncation=False, verbose=False)["input_ids"]
                enc = self.tokenizer(
                    chunk,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                ).to(self.device)
                with torch.inference_mode():
                    logits = self.model(**enc).logits.float()
                probs = torch.softmax(logits, dim=-1).cpu()
                logits = logits.cpu()
                mask = enc["attention_mask"].bool().cpu()
                ids = enc["input_ids"].cpu()

                for row in range(len(chunk)):
                    row_ids = ids[row][mask[row]].tolist()
                    top = int(torch.argmax(probs[row]))
                    results.append(
                        Prediction(
                            label=self.spec.labels[top],
                            score=round(float(probs[row, top]), 6),
                            probs=[
                                LabelScore(
                                    label=self.spec.labels[i],
                                    score=round(float(probs[row, i]), 6),
                                    logit=round(float(logits[row, i]), 4),
                                )
                                for i in order
                            ],
                            tokens=self.tokenizer.convert_ids_to_tokens(row_ids),
                            num_tokens=len(full[row]),
                            truncated=len(full[row]) > self.max_length,
                        )
                    )

            if explain and explain_steps > 0:
                results = [
                    self._with_explanation(original, text, result, explain_steps)
                    for original, text, result in zip(texts, prepared, results, strict=True)
                ]
        return results

    def _with_explanation(
        self, original: str, prepared: str, result: Prediction, steps: int
    ) -> Prediction:
        attributions = integrated_gradients(
            self.model,
            self.tokenizer,
            prepared,
            polarity=self._polarity,
            max_length=self.max_length,
            steps=steps,
        )
        words = word_attributions(original, prepared, attributions)
        return replace(result, attributions=[Attribution(t, w) for t, w in words])


def _warn_on_label_mismatch(spec: ModelSpec, model: PreTrainedModel) -> None:
    id2label = getattr(model.config, "id2label", None) or {}
    names = [str(id2label.get(i, "")).lower() for i in range(len(spec.labels))]
    if all(n.startswith("label_") for n in names):
        return  # generic names; the catalog is the source of truth
    if names != [label.lower() for label in spec.labels]:
        logger.warning(
            "%s: checkpoint labels %s differ from the catalog %s; using the catalog",
            spec.id,
            names,
            list(spec.labels),
        )
