from tests.conftest import FakeProvider


def test_health(make_client):
    client = make_client(FakeProvider("ollama", local=True))
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_models_lists_local_first_and_picks_local_default(make_client):
    client = make_client(
        FakeProvider("ollama", local=True, models=["llama3.2:latest", "qwen3:8b"]),
        FakeProvider("openai", models=["gpt-x"]),
    )
    body = client.get("/api/models").json()
    assert [p["id"] for p in body["providers"]] == ["ollama", "openai"]
    assert body["has_local_models"] is True
    assert body["default"] == {
        "id": "llama3.2:latest",
        "name": "llama3.2:latest",
        "provider": "ollama",
        "local": True,
        "size_bytes": None,
        "parameter_size": None,
        "family": None,
    }


def test_models_default_is_cloud_when_no_local_models(make_client):
    client = make_client(
        FakeProvider("ollama", local=True, models=[]),
        FakeProvider("anthropic", models=["claude-a", "claude-b"], default_model="claude-b"),
    )
    body = client.get("/api/models").json()
    assert body["has_local_models"] is False
    assert body["default"]["provider"] == "anthropic"
    assert body["default"]["id"] == "claude-b"


def test_models_reports_unreachable_and_unconfigured_providers(make_client):
    client = make_client(
        FakeProvider("ollama", local=True, list_error="Ollama is not reachable"),
        FakeProvider("gemini", configured=False),
    )
    providers = {p["id"]: p for p in client.get("/api/models").json()["providers"]}
    assert providers["ollama"]["available"] is False
    assert providers["ollama"]["error"] == "Ollama is not reachable"
    assert providers["gemini"]["configured"] is False
    assert providers["gemini"]["available"] is False
