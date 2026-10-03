# Providers

## Built in

| id | Label | SDK | Endpoint (default) | Env |
|---|---|---|---|---|
| `ollama` | Ollama (local) | `ollama` | `http://localhost:11434` | `OLLAMA_HOST`, `OLLAMA_ENABLED` |
| `anthropic` | Anthropic Claude | `anthropic` | SDK default | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| `openai` | OpenAI | `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| `gemini` | Google Gemini | `openai` (compat) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL` |
| `grok` | xAI Grok | `openai` (compat) | `https://api.x.ai/v1` | `GROK_API_KEY`, `GROK_BASE_URL`, `GROK_MODEL` |
| `meta` | Meta Llama | `openai` (compat) | `https://api.llama.com/compat/v1/` | `META_API_KEY`, `META_BASE_URL`, `META_MODEL` |

A cloud provider is **enabled when its key is set**. Order of cloud fallback:
`CLOUD_PRIORITY=["anthropic","openai","gemini","grok","meta"]`.

Model lists come from each provider's live `models.list()` endpoint, so never
hard-code model ids in code. `*_MODEL` picks the preferred fallback model; when
empty the first listed model is used (Anthropic lists newest first; other lists
are sorted alphabetically, so **set `*_MODEL` for predictable fallback**). If a
compat provider can't list models but `*_MODEL` is set, that model is offered.

Endpoints and model names change. Before shipping, confirm base URLs and good
default model ids in each provider's current docs.

## Adding an OpenAI-compatible provider (most common)

Examples: Mistral, Groq, DeepSeek, Together, OpenRouter, Azure OpenAI v1,
vLLM/LM Studio/llama.cpp servers.

1. `api/app/core/config.py` — add settings:

   ```python
   mistral_api_key: SecretStr | None = None
   mistral_base_url: str = "https://api.mistral.ai/v1"
   mistral_model: str = ""
   ```

2. `api/app/providers/registry.py` → `build_providers()` — add to `cloud`:

   ```python
   "mistral": compat("mistral", "Mistral", s.mistral_api_key, s.mistral_base_url, s.mistral_model),
   ```

   Pass `model_filter=` if the provider lists non-chat models (see
   `_chat_capable_openai` for the pattern).

3. Add `"mistral"` to the `CLOUD_PRIORITY` default and to `.env.example`
   (key, base URL, model).

4. Test: extend `test_build_providers_orders_local_then_cloud_priority` in
   `tests/test_providers.py` and update its expected id set.

No frontend change is needed: the model picker renders whatever `/api/models` returns.

## Adding a provider with its own SDK

1. Create `api/app/providers/<name>.py` implementing `Provider` (copy
   `anthropic.py` as the pattern):
   - `configured` → client exists.
   - `list_models()` → `ModelInfo(id, name, provider=self.id, local=False)`;
     wrap SDK errors in `ProviderError`.
   - `stream_chat()` → `yield` text chunks; map auth / rate-limit / generic
     errors to `ProviderError` with short, user-safe messages.
   - Convert `system` messages if the SDK takes them separately.
   - `aclose()` → close the client.
2. Register it in `build_providers()` and settings as above.
3. Add unit tests that monkeypatch the SDK client (see
   `test_ollama_streams_deltas` for the style). Never call real networks in tests.

## Another local runtime (LM Studio, llama.cpp, vLLM)

These expose OpenAI-compatible servers. Add them with `compat(...)` but give the
provider `local = True` after construction so they sort with local models and
show the local badge:

```python
lmstudio = compat("lmstudio", "LM Studio (local)", SecretStr("lm-studio"), "http://localhost:1234/v1", "")
lmstudio.local = True
return [local, lmstudio, *ordered]
```

## Error message conventions

| Situation | Message pattern |
|---|---|
| Unreachable local server | `Ollama is not reachable at <host>` |
| Missing key | `<Label> is not configured (missing API key)` |
| Bad key | `<Label>: invalid API key` |
| Quota | `<Label>: rate limit or quota exceeded` |
| Other API error | `<Label>: <sdk message>` |

These strings reach end users (fallback notice, error bubble), so keep them
short and never include keys, headers or stack traces.
