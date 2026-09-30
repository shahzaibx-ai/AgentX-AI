"""The sentiment models the API can serve.

Each entry mirrors the checkpoint's own `config.json` (label order = `id2label`).
Weights are always loaded from safetensors: transformers refuses pickled
`pytorch_model.bin` files on torch < 2.6 (CVE-2025-32434), and this project pins
torch 2.2.2. Two repos publish safetensors only on the Hugging Face conversion
bot's pull-request revision, so those are pinned below.
"""

import re
from dataclasses import dataclass
from typing import Literal

Preprocess = Literal["none", "twitter"]


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    domain: str
    description: str
    languages: str
    parameters: str
    architecture: str
    labels: tuple[str, ...]
    """Label names in the checkpoint's index order (its `id2label`)."""
    polarity: tuple[float, ...]
    """Sentiment direction of each label, from -1 (negative) to +1 (positive)."""
    revision: str = "main"
    preprocess: Preprocess = "none"

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.polarity):
            raise ValueError(f"{self.id}: labels and polarity must have the same length")

    @property
    def display_order(self) -> tuple[int, ...]:
        """Label indices from most negative to most positive (a stable order for the UI)."""
        return tuple(sorted(range(len(self.labels)), key=lambda i: self.polarity[i]))

    def prepare(self, text: str) -> str:
        """Model-specific input cleanup. Keeps the whitespace layout of `text` intact."""
        if self.preprocess == "twitter":
            return _twitter_preprocess(text)
        return text


def _twitter_preprocess(text: str) -> str:
    # As recommended by cardiffnlp: mask user handles and links.
    def swap(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("@") and len(token) > 1:
            return "@user"
        if token.startswith("http"):
            return "http"
        return token

    return re.sub(r"\S+", swap, text)


FINBERT = ModelSpec(
    id="ProsusAI/finbert",
    name="FinBERT",
    domain="Financial",
    description="Financial news, filings and analyst commentary.",
    languages="English",
    parameters="110M",
    architecture="BertForSequenceClassification",
    labels=("positive", "negative", "neutral"),
    polarity=(1.0, -1.0, 0.0),
    revision="refs/pr/29",  # safetensors conversion of main
)

DISTILBERT_SST2 = ModelSpec(
    id="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    name="DistilBERT SST-2",
    domain="Topic",
    description="General short text: reviews, comments, headlines. Positive or negative.",
    languages="English",
    parameters="67M",
    architecture="DistilBertForSequenceClassification",
    labels=("negative", "positive"),
    polarity=(-1.0, 1.0),
)

TWITTER_ROBERTA = ModelSpec(
    id="cardiffnlp/twitter-roberta-base-sentiment-latest",
    name="Twitter RoBERTa",
    domain="Social media",
    description="Tweets and short social posts, including a neutral class.",
    languages="English",
    parameters="125M",
    architecture="RobertaForSequenceClassification",
    labels=("negative", "neutral", "positive"),
    polarity=(-1.0, 0.0, 1.0),
    revision="refs/pr/43",  # safetensors conversion of main
    preprocess="twitter",
)

MULTILINGUAL_STARS = ModelSpec(
    id="nlptown/bert-base-multilingual-uncased-sentiment",
    name="Multilingual BERT",
    domain="Product reviews",
    description="Product reviews rated from 1 to 5 stars.",
    languages="English, Dutch, German, French, Spanish, Italian",
    parameters="167M",
    architecture="BertForSequenceClassification",
    labels=("1 star", "2 stars", "3 stars", "4 stars", "5 stars"),
    polarity=(-1.0, -0.5, 0.0, 0.5, 1.0),
)

CATALOG: dict[str, ModelSpec] = {
    spec.id: spec for spec in (DISTILBERT_SST2, FINBERT, TWITTER_ROBERTA, MULTILINGUAL_STARS)
}
DEFAULT_MODEL_ID = DISTILBERT_SST2.id
