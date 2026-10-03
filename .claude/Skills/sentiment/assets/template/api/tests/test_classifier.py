from pathlib import Path

import pytest
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.ml.catalog import (
    CATALOG,
    DISTILBERT_SST2,
    FINBERT,
    MULTILINGUAL_STARS,
    TWITTER_ROBERTA,
    ModelSpec,
)
from app.ml.classifier import SentimentClassifier
from app.ml.explain import integrated_gradients, segments, word_weights

CPU = torch.device("cpu")


def load(spec: ModelSpec, model_dirs: dict[str, Path], **kw: object) -> SentimentClassifier:
    return SentimentClassifier.load(spec, source=model_dirs[spec.id], device=CPU, **kw)


# ---------------------------------------------------------------- catalog
def test_catalog_matches_published_checkpoints():
    assert FINBERT.labels == ("positive", "negative", "neutral")
    assert DISTILBERT_SST2.labels == ("negative", "positive")
    assert TWITTER_ROBERTA.labels == ("negative", "neutral", "positive")
    assert MULTILINGUAL_STARS.labels == tuple(
        f"{n} star{'s' if n > 1 else ''}" for n in range(1, 6)
    )
    # Repos whose main branch only has pickled weights are pinned to safetensors revisions.
    assert FINBERT.revision == "refs/pr/29"
    assert TWITTER_ROBERTA.revision == "refs/pr/43"
    assert len(CATALOG) == 4


def test_display_order_runs_negative_to_positive():
    assert [FINBERT.labels[i] for i in FINBERT.display_order] == ["negative", "neutral", "positive"]
    assert [MULTILINGUAL_STARS.labels[i] for i in MULTILINGUAL_STARS.display_order] == [
        "1 star",
        "2 stars",
        "3 stars",
        "4 stars",
        "5 stars",
    ]


def test_twitter_preprocessing_masks_handles_and_links_keeping_layout():
    text = "@rizwan  loved it!\nsee https://x.co/a @ ok"
    assert TWITTER_ROBERTA.prepare(text) == "@user  loved it!\nsee http @ ok"
    assert len(segments(TWITTER_ROBERTA.prepare(text))) == len(segments(text))
    assert FINBERT.prepare(text) == text


# ---------------------------------------------------------------- predictions
@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        (FINBERT, "neutral"),  # index 2 in FinBERT's own order
        (DISTILBERT_SST2, "positive"),
        (TWITTER_ROBERTA, "negative"),
        (MULTILINGUAL_STARS, "4 stars"),
    ],
)
def test_labels_follow_the_checkpoint_order(model_dirs, spec, expected):
    (result,) = load(spec, model_dirs).predict(["The service was good but the food was bad."])
    assert result.label == expected
    assert result.score > 0.9
    assert [p.label for p in result.probs] == [spec.labels[i] for i in spec.display_order]
    assert sum(p.score for p in result.probs) == pytest.approx(1.0, abs=1e-4)
    assert result.probs[[p.label for p in result.probs].index(expected)].score == result.score


def test_matches_a_plain_transformers_forward_pass(model_dirs):
    path = model_dirs[FINBERT.id]
    text = "Shares rose after strong quarterly earnings."
    tokenizer = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path).eval()
    with torch.no_grad():
        expected = torch.softmax(model(**tokenizer(text, return_tensors="pt")).logits, -1)[0]
    (result,) = load(FINBERT, model_dirs).predict([text])
    by_label = {p.label: p.score for p in result.probs}
    for index, label in enumerate(FINBERT.labels):
        assert by_label[label] == pytest.approx(float(expected[index]), abs=1e-5)


def test_batches_match_single_predictions(model_dirs):
    texts = ["good", "The hotel room was clean and the staff were friendly.", "bad " * 40, "ok"]
    classifier = load(DISTILBERT_SST2, model_dirs, batch_size=3)
    batch = classifier.predict(texts)
    singles = [classifier.predict([t])[0] for t in texts]
    for b, s in zip(batch, singles, strict=True):
        assert b.label == s.label
        for pb, ps in zip(b.probs, s.probs, strict=True):
            assert pb.score == pytest.approx(ps.score, abs=1e-4)
        assert b.tokens == s.tokens  # padding is removed from the token list


def test_tokens_and_truncation(model_dirs):
    classifier = load(DISTILBERT_SST2, model_dirs, max_length=16)
    short, long = classifier.predict(["I love it", "good " * 40])
    assert short.tokens[0] == "[CLS]" and short.tokens[-1] == "[SEP]"
    assert short.num_tokens == len(short.tokens) and not short.truncated
    assert long.truncated and long.num_tokens == 42 and len(long.tokens) == 16


def test_roberta_respects_its_position_limit(model_dirs):
    classifier = load(TWITTER_ROBERTA, model_dirs)
    assert classifier.max_length == 512  # 514 positions minus RoBERTa's padding offset
    (result,) = classifier.predict(["great " * 700])
    assert result.truncated and len(result.tokens) == 512


def test_refuses_pickled_weights(model_dirs, tmp_path):
    """torch 2.2 cannot load .bin files safely; only safetensors checkpoints are accepted."""
    source = model_dirs[DISTILBERT_SST2.id]
    model = AutoModelForSequenceClassification.from_pretrained(source)
    AutoTokenizer.from_pretrained(source).save_pretrained(tmp_path)
    model.save_pretrained(tmp_path, safe_serialization=False)
    assert (tmp_path / "pytorch_model.bin").exists()
    with pytest.raises(OSError, match=r"safetensors"):
        SentimentClassifier.load(DISTILBERT_SST2, source=tmp_path, device=CPU)


def test_rejects_a_checkpoint_with_the_wrong_number_of_labels(model_dirs):
    with pytest.raises(ValueError, match="labels"):
        SentimentClassifier.load(FINBERT, source=model_dirs[DISTILBERT_SST2.id], device=CPU)


# ---------------------------------------------------------------- explanations
@pytest.mark.parametrize("spec", [FINBERT, DISTILBERT_SST2, TWITTER_ROBERTA, MULTILINGUAL_STARS])
def test_integrated_gradients_is_complete(model_dirs, spec):
    """IG's completeness axiom: attributions sum to f(input) - f(baseline)."""
    classifier = load(spec, model_dirs)
    result = integrated_gradients(
        classifier.model,
        classifier.tokenizer,
        "The service was good but the food was bad.",
        polarity=torch.tensor(spec.polarity),
        max_length=512,
        steps=64,
    )
    gap = result.target - result.baseline
    assert sum(result.scores) == pytest.approx(gap, abs=max(1e-4, abs(gap) * 0.05))


@pytest.mark.parametrize("spec", [DISTILBERT_SST2, TWITTER_ROBERTA])
def test_explanation_covers_every_word_of_the_original(model_dirs, spec):
    text = "@rizwan  The battery life is great,\nbut delivery was slow!"
    (result,) = load(spec, model_dirs).predict([text], explain=True, explain_steps=8)
    assert result.attributions is not None
    assert "".join(a.text for a in result.attributions) == text  # original, not "@user"
    words = [a for a in result.attributions if a.text.strip()]
    assert all(-1.0 <= a.weight <= 1.0 for a in result.attributions)
    assert max(abs(a.weight) for a in words) == pytest.approx(1.0)
    assert all(a.weight == 0 for a in result.attributions if not a.text.strip())


def test_explanations_are_off_by_default_and_with_zero_steps(model_dirs):
    classifier = load(DISTILBERT_SST2, model_dirs)
    assert classifier.predict(["good"])[0].attributions is None
    assert classifier.predict(["good"], explain=True, explain_steps=0)[0].attributions is None


def test_unknown_tokens_are_attributed(model_dirs):
    """[UNK] (an emoji for an uncased BERT) is text, not a special token."""
    (result,) = load(DISTILBERT_SST2, model_dirs).predict(
        ["love 😍 it"], explain=True, explain_steps=16
    )
    emoji = next(a for a in result.attributions if a.text == "😍")
    assert "[UNK]" in result.tokens
    assert emoji.weight != 0.0


@pytest.mark.parametrize("spec", [DISTILBERT_SST2, TWITTER_ROBERTA])
def test_word_weights_keep_every_token_score(model_dirs, spec):
    """Nothing is dropped when tokens map to words, including whitespace-only BPE tokens."""
    classifier = load(spec, model_dirs)
    text = spec.prepare("love  it\tok 😍\n@rizwan   was   great ")
    attributions = integrated_gradients(
        classifier.model,
        classifier.tokenizer,
        text,
        polarity=torch.tensor(spec.polarity),
        max_length=512,
        steps=8,
    )
    weights = word_weights(text, attributions)
    assert sum(weights) == pytest.approx(sum(attributions.scores), abs=1e-6)
    spaces = [w for (seg, _, _), w in zip(segments(text), weights, strict=True) if not seg.strip()]
    assert all(w == 0.0 for w in spaces)
