import threading
import time

import pytest
import torch
from fastapi.testclient import TestClient

from app.factory import create_app
from app.ml.catalog import CATALOG, DISTILBERT_SST2, FINBERT, MULTILINGUAL_STARS
from app.ml.registry import ModelRegistry

TEXT = "The hotel room was clean and the staff were friendly, but the wifi was slow."


# ---------------------------------------------------------------- health & models
def test_health_reports_device_and_model_status(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["device"] == "cpu"
    assert set(body["models"]) == set(CATALOG)
    assert set(body["models"].values()) == {"not_loaded"}


def test_models_lists_the_catalog_with_limits(client):
    body = client.get("/api/models").json()
    assert body["default_model"] == DISTILBERT_SST2.id
    assert body["limits"] == {
        "max_length": 512,
        "max_text_chars": 5000,
        "max_batch_items": 1000,
        "batch_size": 32,
        "explain_steps": 8,
        "low_confidence": 0.6,
    }
    finbert = next(m for m in body["models"] if m["id"] == FINBERT.id)
    assert finbert["labels"] == ["negative", "neutral", "positive"]
    assert finbert["domain"] == "Financial"
    assert finbert["revision"] == "refs/pr/29"
    assert finbert["status"] == "not_loaded" and finbert["default"] is False


def test_load_endpoint_warms_a_model(client):
    res = client.post("/api/models/load", json={"model": FINBERT.id})
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    assert client.get("/api/health").json()["models"][FINBERT.id] == "ready"


def test_enabled_models_limit_the_catalog(make_settings):
    settings = make_settings(enabled_models=[FINBERT.id], default_model=FINBERT.id)
    with TestClient(create_app(settings)) as c:
        assert [m["id"] for m in c.get("/api/models").json()["models"]] == [FINBERT.id]
        res = c.post("/api/predict", json={"text": "hi", "model": DISTILBERT_SST2.id})
        assert res.status_code == 404


# ---------------------------------------------------------------- predict
def test_predict_uses_the_default_model_with_explanations(client):
    res = client.post("/api/predict", json={"text": TEXT})
    assert res.status_code == 200
    body = res.json()
    assert body["model"] == DISTILBERT_SST2.id
    assert body["label"] == "positive"
    assert [p["label"] for p in body["probs"]] == ["negative", "positive"]
    assert body["device"] == "cpu" and body["latency_ms"] >= 0
    assert body["tokens"][0] == "[CLS]" and body["num_tokens"] == len(body["tokens"])
    assert body["truncated"] is False
    assert "".join(a["text"] for a in body["attributions"]) == TEXT


def test_predict_with_a_chosen_model_and_no_explanation(client):
    res = client.post(
        "/api/predict", json={"text": TEXT, "model": MULTILINGUAL_STARS.id, "explain": False}
    )
    body = res.json()
    assert body["label"] == "4 stars"
    assert body["probs"][0]["label"] == "1 star"
    assert body["attributions"] is None


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"text": "   "}, "Text is empty"),
        ({"text": ""}, "at least 1 character"),
        ({}, "Field required"),
    ],
)
def test_predict_validation(client, payload, message):
    res = client.post("/api/predict", json=payload)
    assert res.status_code == 422
    assert message in str(res.json()["detail"])


def test_predict_rejects_text_over_the_limit(make_settings):
    with TestClient(create_app(make_settings(max_text_chars=20))) as c:
        res = c.post("/api/predict", json={"text": "x" * 21})
        assert res.status_code == 422
        assert res.json()["detail"] == "The text has 21 characters; the limit is 20"


def test_unknown_model_is_404(client):
    res = client.post("/api/predict", json={"text": "hi", "model": "someone/other"})
    assert res.status_code == 404
    assert "Available:" in res.json()["detail"]


# ---------------------------------------------------------------- batch
def test_batch_returns_one_result_per_text_in_order(client):
    texts = [TEXT, "Terrible delivery.", "ok"]
    res = client.post("/api/predict/batch", json={"texts": texts, "model": FINBERT.id})
    assert res.status_code == 200
    body = res.json()
    assert body["model"] == FINBERT.id
    assert len(body["results"]) == 3
    assert all(r["label"] == "neutral" for r in body["results"])
    assert "tokens" not in body["results"][0] and "attributions" not in body["results"][0]


def test_batch_validation(make_settings):
    with TestClient(create_app(make_settings(max_batch_items=2, max_text_chars=10))) as c:
        too_many = c.post("/api/predict/batch", json={"texts": ["a", "b", "c"]})
        assert too_many.status_code == 422
        assert too_many.json()["detail"] == "3 texts sent; the limit is 2 per request"
        too_long = c.post("/api/predict/batch", json={"texts": ["ok", "x" * 11]})
        assert too_long.json()["detail"] == "Row 2 has 11 characters; the limit is 10"
        blank = c.post("/api/predict/batch", json={"texts": ["ok", " "]})
        assert "Row 2 is empty" in str(blank.json()["detail"])
        empty = c.post("/api/predict/batch", json={"texts": []})
        assert empty.status_code == 422


# ---------------------------------------------------------------- loading
def test_load_failure_is_a_clear_503_and_is_retried(make_settings):
    attempts = []

    def flaky(spec, device):
        attempts.append(spec.id)
        raise OSError("We couldn't connect to 'https://huggingface.co' to load the files")

    settings = make_settings()
    registry = ModelRegistry(settings, loader=flaky)
    with TestClient(create_app(settings, registry)) as c:
        res = c.post("/api/predict", json={"text": "hi"})
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail.startswith("Couldn't load DistilBERT SST-2: We couldn't connect")
        assert "uv run python -m app.download" in detail
        model = next(m for m in c.get("/api/models").json()["models"] if m["default"])
        assert model["status"] == "error" and model["error"] == detail
        c.post("/api/predict", json={"text": "hi"})
    assert len(attempts) == 2


def test_startup_preload_runs_in_the_background(make_settings):
    gate = threading.Event()
    settings = make_settings(preload_models=[FINBERT.id])
    real = ModelRegistry(settings)

    def slow(spec, device):
        gate.wait(5)
        return real._load(spec, device)

    registry = ModelRegistry(settings, loader=slow)
    with TestClient(create_app(settings, registry)) as c:
        assert c.get("/api/health").json()["models"][FINBERT.id] == "loading"
        gate.set()
        for _ in range(100):
            if c.get("/api/health").json()["models"][FINBERT.id] == "ready":
                break
            time.sleep(0.05)
        assert c.get("/api/health").json()["models"][FINBERT.id] == "ready"


def test_concurrent_first_requests_load_the_model_once(make_settings):
    loads = []
    settings = make_settings()
    real = ModelRegistry(settings)

    def counting(spec, device):
        loads.append(spec.id)
        time.sleep(0.2)
        return real._load(spec, device)

    registry = ModelRegistry(settings, loader=counting)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(registry.get(FINBERT.id))) for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert loads == [FINBERT.id]
    assert len({id(r) for r in results}) == 1


# ---------------------------------------------------------------- settings
def test_settings_validation(make_settings):
    with pytest.raises(ValueError, match="Unknown models"):
        make_settings(enabled_models=["nope/model"])
    with pytest.raises(ValueError, match="DEFAULT_MODEL"):
        make_settings(enabled_models=[FINBERT.id])
    with pytest.raises(ValueError, match="PRELOAD_MODELS"):
        make_settings(enabled_models=[FINBERT.id], default_model=FINBERT.id, preload_models=["x"])


def test_docs_are_hidden_in_production(make_settings):
    with TestClient(create_app(make_settings(environment="production"))) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
    with TestClient(create_app(make_settings())) as c:
        assert c.get("/docs").status_code == 200


def test_cors_allows_the_web_app(client):
    res = client.options(
        "/api/predict",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_torch_is_the_pinned_version():
    assert torch.__version__.startswith("2.2.2")
