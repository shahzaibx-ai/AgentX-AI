"""Offline tests for check_model.py's decisions.

Run from a project's api/ folder (the last test imports its catalog):
    cd api && uv run pytest <skill>/scripts/test_check_model.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, os.getcwd())

from check_model import Candidate, choose_revision, guess_polarity, render_spec, tokenizer_note


def test_prefers_main_when_it_has_safetensors():
    chosen = choose_revision(
        ["config.json", "model.safetensors"], [Candidate("refs/pr/9", ["model.safetensors"])]
    )
    assert chosen.revision == "main"


def test_falls_back_to_newest_bot_pr_with_safetensors():
    prs = [
        Candidate("refs/pr/8", ["model.safetensors"]),
        Candidate("refs/pr/29", ["model.safetensors"]),
        Candidate("refs/pr/30", ["pytorch_model.bin"]),
    ]
    assert choose_revision(["pytorch_model.bin"], prs).revision == "refs/pr/29"


def test_sharded_safetensors_count():
    assert choose_revision(["model.safetensors.index.json"], []).revision == "main"


def test_no_safetensors_anywhere():
    assert choose_revision(["pytorch_model.bin"], [Candidate("refs/pr/1", ["README.md"])]) is None


def test_polarity_from_label_names():
    assert guess_polarity(["positive", "negative", "neutral"]) == [1.0, -1.0, 0.0]
    assert guess_polarity(["NEGATIVE", "POSITIVE"]) == [-1.0, 1.0]
    assert guess_polarity(["1 star", "2 stars", "3 stars", "4 stars", "5 stars"]) == [
        -1.0,
        -0.5,
        0.0,
        0.5,
        1.0,
    ]
    assert guess_polarity(["LABEL_0", "LABEL_1"]) is None


def test_tokenizer_detection():
    assert tokenizer_note(["vocab.txt"])[0]
    assert tokenizer_note(["vocab.json", "merges.txt"])[0]
    assert not tokenizer_note(["spiece.model"])[0]


def test_rendered_spec_is_valid_python_matching_the_catalog_type():
    code = render_spec(
        "ProsusAI/finbert",
        "refs/pr/29",
        ["positive", "negative", "neutral"],
        [1.0, -1.0, 0.0],
        "BertForSequenceClassification",
        domain="Financial",
    )
    from app.ml.catalog import ModelSpec

    namespace = {"ModelSpec": ModelSpec}
    exec(code, namespace)
    spec = namespace["FINBERT"]
    assert spec.revision == "refs/pr/29"
    assert spec.labels == ("positive", "negative", "neutral")
    assert [spec.labels[i] for i in spec.display_order] == ["negative", "neutral", "positive"]
