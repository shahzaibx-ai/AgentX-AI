"""Word-level explanations with integrated gradients.

The attributed quantity is the prediction's *polarity*: sum(p_label * polarity_label),
so a positive weight means "pushed toward positive sentiment" for every model,
including 3-class and 1-5 star models.

Integrated gradients (Sundararajan et al., 2017) interpolates from a baseline
(every ordinary token replaced by [PAD], special tokens kept) to the real input
embeddings and accumulates the gradients along the path. Token attributions are
then summed onto the whitespace-separated words of the original text.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

import torch
from transformers import PreTrainedModel, PreTrainedTokenizerBase

_SEGMENT = re.compile(r"\s+|\S+")


@dataclass(frozen=True)
class TokenAttributions:
    input_ids: list[int]
    offsets: list[tuple[int, int]]
    scores: list[float]
    """Raw attribution per token (0 for special tokens)."""
    target: float
    """Polarity of the real input."""
    baseline: float
    """Polarity of the baseline input."""


def segments(text: str) -> list[tuple[str, int, int]]:
    """Split text into alternating word / whitespace segments with their spans."""
    return [(m.group(0), m.start(), m.end()) for m in _SEGMENT.finditer(text)]


def integrated_gradients(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    text: str,
    *,
    polarity: torch.Tensor,
    max_length: int,
    steps: int,
    chunk_size: int = 8,
) -> TokenAttributions:
    device = next(model.parameters()).device
    enc = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        return_offsets_mapping=True,
        return_special_tokens_mask=True,
        return_tensors="pt",
    )
    offsets = [tuple(pair) for pair in enc.pop("offset_mapping")[0].tolist()]
    # Only tokens the tokenizer added ([CLS], [SEP], <s>, </s>) are special here;
    # [UNK] (e.g. an emoji for an uncased BERT) is part of the text and gets attributed.
    special = enc.pop("special_tokens_mask")[0].bool().to(device)
    enc = enc.to(device)
    input_ids = enc["input_ids"]
    attention_mask = enc["attention_mask"]
    extra = {k: v for k, v in enc.items() if k not in ("input_ids", "attention_mask")}

    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
    baseline_ids = torch.where(special, input_ids[0], torch.full_like(input_ids[0], pad_id))

    embed = model.get_input_embeddings()
    polarity = polarity.to(device)
    with torch.no_grad():
        inputs = embed(input_ids).float()
        baseline = embed(baseline_ids.unsqueeze(0)).float()
    delta = inputs - baseline

    def score(embeds: torch.Tensor) -> torch.Tensor:
        n = embeds.shape[0]
        out = model(
            inputs_embeds=embeds,
            attention_mask=attention_mask.expand(n, -1),
            **{k: v.expand(n, -1) for k, v in extra.items()},
        )
        return (torch.softmax(out.logits.float(), dim=-1) * polarity).sum(dim=-1)

    # Midpoint Riemann sum over the straight-line path.
    alphas = (torch.arange(steps, device=device, dtype=torch.float32) + 0.5) / steps
    total = torch.zeros_like(inputs[0])
    with torch.enable_grad():
        for start in range(0, steps, chunk_size):
            a = alphas[start : start + chunk_size].view(-1, 1, 1)
            path = (baseline + a * delta).detach().requires_grad_(True)
            (grads,) = torch.autograd.grad(score(path).sum(), path)
            total += grads.sum(dim=0)

    token_scores = (delta[0] * total / steps).sum(dim=-1)
    token_scores = token_scores.masked_fill(special, 0.0)

    with torch.no_grad():
        ends = score(torch.cat([inputs, baseline])).tolist()

    return TokenAttributions(
        input_ids=input_ids[0].tolist(),
        offsets=offsets,
        scores=token_scores.detach().cpu().tolist(),
        target=ends[0],
        baseline=ends[1],
    )


def word_attributions(
    original: str, prepared: str, attributions: TokenAttributions
) -> list[tuple[str, float]]:
    """Sum token scores onto the words of `original`, normalised to [-1, 1].

    `prepared` is the text the model saw; model preprocessing replaces whole words
    only, so its segments line up one-to-one with the original's.
    """
    orig_segments = segments(original)
    if len(orig_segments) != len(segments(prepared)):  # defensive: fall back to model text
        orig_segments = segments(prepared)
    weights = word_weights(prepared, attributions)
    peak = max((abs(w) for w in weights), default=0.0)
    scale = 1.0 / peak if peak > 1e-12 else 0.0
    return [(text, round(weights[i] * scale, 4)) for i, (text, _, _) in enumerate(orig_segments)]


def word_weights(prepared: str, attributions: TokenAttributions) -> list[float]:
    """Raw attribution per segment of `prepared`; whitespace segments stay 0."""
    prep_segments = segments(prepared)
    if not prep_segments:
        return []
    starts = [s for _, s, _ in prep_segments]
    is_space = [not text.strip() for text, _, _ in prep_segments]
    weights = [0.0] * len(prep_segments)

    for (start, end), value in zip(attributions.offsets, attributions.scores, strict=True):
        if value == 0.0:
            continue  # special tokens (zeroed) and exact zeros
        # Byte-level BPE offsets can include the leading space: use the first non-space char.
        pos = start
        while pos < end and prepared[pos].isspace():
            pos += 1
        index = max(0, bisect_right(starts, pos) - 1)
        if is_space[index]:
            # A whitespace-only token (RoBERTa's extra "Ġ", tabs, newlines): credit the
            # next word, or the previous one at the end of the text.
            if index + 1 < len(prep_segments):
                index += 1
            elif index > 0:
                index -= 1
        weights[index] += value
    return weights
