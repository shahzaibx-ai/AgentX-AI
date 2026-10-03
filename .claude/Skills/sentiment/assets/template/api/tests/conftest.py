"""Tiny, real checkpoints built on the fly (no network).

Each one has the architecture, tokenizer type and label order of a catalog model,
but only a few thousand parameters, so the whole PyTorch/Transformers path runs
in milliseconds.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import torch
from fastapi.testclient import TestClient
from tokenizers import ByteLevelBPETokenizer
from transformers import (
    BertConfig,
    BertForSequenceClassification,
    BertTokenizerFast,
    DistilBertConfig,
    DistilBertForSequenceClassification,
    DistilBertTokenizerFast,
    RobertaConfig,
    RobertaForSequenceClassification,
    RobertaTokenizerFast,
)

from app.core.config import Settings
from app.factory import create_app
from app.ml.catalog import DISTILBERT_SST2, FINBERT, MULTILINGUAL_STARS, TWITTER_ROBERTA

WORDS = [
    "the",
    "a",
    "an",
    "is",
    "was",
    "were",
    "be",
    "it",
    "this",
    "that",
    "and",
    "but",
    "not",
    "no",
    "very",
    "really",
    "so",
    "i",
    "we",
    "you",
    "they",
    "good",
    "great",
    "excellent",
    "love",
    "amazing",
    "happy",
    "best",
    "fast",
    "friendly",
    "clean",
    "helpful",
    "bad",
    "terrible",
    "awful",
    "hate",
    "worst",
    "slow",
    "rude",
    "broken",
    "dirty",
    "poor",
    "refund",
    "service",
    "food",
    "room",
    "staff",
    "battery",
    "life",
    "delivery",
    "price",
    "quality",
    "support",
    "product",
    "stock",
    "market",
    "profit",
    "loss",
    "revenue",
    "shares",
    "growth",
    "company",
    "quarter",
    "earnings",
    "movie",
    "hotel",
    "phone",
    "app",
    "camera",
    "wifi",
    "breakfast",
    "setup",
    "two",
    "minutes",
    "honestly",
    "de",
    "het",
    "ist",
    "sehr",
    "gut",
    "schlecht",
    "bueno",
    "malo",
    "tres",
    "bien",
]
PUNCT = list(".,!?'-@:/")
SPECIALS = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
CORPUS = [
    "The service was good but the food was bad.",
    "I love this phone, the battery life is great!",
    "Terrible delivery, the product arrived broken.",
    "Shares rose after strong quarterly earnings.",
    "@user the app is slow http://example.com",
] * 20


def _wordpiece_vocab(path: Path) -> Path:
    subwords = ["##s", "##ed", "##ing", "##ly", "##n", "##t", "##er", "##e"]
    letters = [chr(c) for c in range(ord("a"), ord("z") + 1)]
    tokens = SPECIALS + WORDS + subwords + PUNCT + letters + [f"##{c}" for c in letters]
    path.write_text("\n".join(dict.fromkeys(tokens)) + "\n")
    return path


def _bias(model: torch.nn.Module, head: torch.nn.Linear, index: int) -> None:
    """Make the model predict `index` with high confidence, whatever the input."""
    with torch.no_grad():
        head.bias.zero_()
        head.bias[index] = 6.0
    model.eval()


def build_bert(root: Path, labels: tuple[str, ...], favour: int) -> Path:
    out = root / f"bert-{len(labels)}"
    out.mkdir()
    vocab = _wordpiece_vocab(root / f"vocab-{len(labels)}.txt")
    tokenizer = BertTokenizerFast(vocab_file=str(vocab), do_lower_case=True)
    torch.manual_seed(0)
    config = BertConfig(
        vocab_size=tokenizer.vocab_size,
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=64,
        max_position_embeddings=512,
        num_labels=len(labels),
        id2label=dict(enumerate(labels)),
        label2id={label: i for i, label in enumerate(labels)},
    )
    model = BertForSequenceClassification(config)
    _bias(model, model.classifier, favour)
    tokenizer.save_pretrained(out)
    model.save_pretrained(out, safe_serialization=True)
    return out


def build_distilbert(root: Path, favour: int) -> Path:
    out = root / "distilbert"
    out.mkdir()
    vocab = _wordpiece_vocab(root / "vocab-distil.txt")
    tokenizer = DistilBertTokenizerFast(vocab_file=str(vocab), do_lower_case=True)
    torch.manual_seed(1)
    config = DistilBertConfig(
        vocab_size=tokenizer.vocab_size,
        dim=32,
        n_layers=2,
        n_heads=2,
        hidden_dim=64,
        max_position_embeddings=512,
        num_labels=2,
        id2label={0: "NEGATIVE", 1: "POSITIVE"},
        label2id={"NEGATIVE": 0, "POSITIVE": 1},
    )
    model = DistilBertForSequenceClassification(config)
    _bias(model, model.classifier, favour)
    tokenizer.save_pretrained(out)
    model.save_pretrained(out, safe_serialization=True)
    return out


def build_roberta(root: Path, favour: int) -> Path:
    out = root / "roberta"
    out.mkdir()
    bpe = ByteLevelBPETokenizer()
    bpe.train_from_iterator(
        [*CORPUS, " ".join(WORDS)],
        vocab_size=400,
        min_frequency=1,
        special_tokens=["<s>", "<pad>", "</s>", "<unk>", "<mask>"],
    )
    bpe_dir = root / "bpe"
    bpe_dir.mkdir()
    bpe.save_model(str(bpe_dir))
    tokenizer = RobertaTokenizerFast(
        vocab_file=str(bpe_dir / "vocab.json"), merges_file=str(bpe_dir / "merges.txt")
    )
    torch.manual_seed(2)
    config = RobertaConfig(
        vocab_size=tokenizer.vocab_size,
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=64,
        max_position_embeddings=514,
        type_vocab_size=1,
        pad_token_id=tokenizer.pad_token_id,
        num_labels=3,
        id2label={0: "negative", 1: "neutral", 2: "positive"},
        label2id={"negative": 0, "neutral": 1, "positive": 2},
    )
    model = RobertaForSequenceClassification(config)
    _bias(model, model.classifier.out_proj, favour)
    tokenizer.save_pretrained(out)
    model.save_pretrained(out, safe_serialization=True)
    return out


@pytest.fixture(scope="session")
def model_dirs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("models")
    return {
        # FinBERT index order is (positive, negative, neutral): favour index 2 = neutral.
        FINBERT.id: build_bert(root, FINBERT.labels, favour=2),
        DISTILBERT_SST2.id: build_distilbert(root, favour=1),  # positive
        TWITTER_ROBERTA.id: build_roberta(root, favour=0),  # negative
        MULTILINGUAL_STARS.id: build_bert(root, MULTILINGUAL_STARS.labels, favour=3),  # 4 stars
    }


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings also read environment variables: clear them so a shell's exports can't leak in."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)


@pytest.fixture
def make_settings(model_dirs: dict[str, Path]) -> Callable[..., Settings]:
    def factory(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "model_sources": {k: str(v) for k, v in model_dirs.items()},
            "preload_models": [],
            "device": "cpu",
            "explain_steps": 8,
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return factory


@pytest.fixture
def client(make_settings: Callable[..., Settings]) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings())) as test_client:
        yield test_client
