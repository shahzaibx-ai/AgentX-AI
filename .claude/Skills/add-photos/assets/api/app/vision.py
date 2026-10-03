"""Which models can see images.

Ollama reports it directly (`capabilities` contains "vision"). Cloud APIs don't
list capabilities, so these rules follow each provider's published model
families. `VISION_MODELS` in .env adds patterns when a rule misses a model.
"""

from fnmatch import fnmatch

OLLAMA_VISION_FAMILIES = ("clip", "mllama", "qwen25vl", "qwen2vl", "gemma3", "mistral3", "llama4")
OLLAMA_VISION_NAMES = (
    "llava", "bakllava", "vision", "moondream", "minicpm-v", "qwen2.5vl", "qwen2-vl", "qwen3-vl",
    "gemma3", "llama4", "mistral-small3.1", "mistral-small3.2", "granite3.2-vision",
)  # fmt: skip


def ollama_vision(name: str, capabilities: list[str] | None, families: list[str] | None) -> bool:
    """Prefer Ollama's own report; older servers without it fall back to known families/names."""
    if capabilities is not None:
        return "vision" in capabilities
    lower = name.lower()
    # Text-only relatives of vision families.
    if lower.startswith(("gemma3:1b", "gemma3:270m", "gemma3n")):
        return False
    if any(f in OLLAMA_VISION_FAMILIES for f in (families or [])):
        return True
    return any(n in lower for n in OLLAMA_VISION_NAMES)


def _anthropic(m: str) -> bool:
    return m.startswith("claude") and not m.startswith(("claude-2", "claude-instant"))


def _openai(m: str) -> bool:
    text_only = ("gpt-3.5", "o1-mini", "o1-preview", "o3-mini", "gpt-4-turbo-preview", "gpt-4-0")
    if m.startswith(text_only) or m in ("gpt-4", "gpt-4-32k"):
        return False
    return m.startswith(("gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-4.5", "gpt-5", "chatgpt-4o",
                         "o1", "o3", "o4"))  # fmt: skip


CLOUD_RULES = {
    "anthropic": _anthropic,
    "openai": _openai,
    "gemini": lambda m: m.startswith("gemini"),
    "grok": lambda m: "vision" in m or m.startswith(("grok-4", "grok-5")),
    "meta": lambda m: "llama-4" in m or "vision" in m,
}


def cloud_vision(provider: str, model_id: str) -> bool:
    rule = CLOUD_RULES.get(provider)
    return bool(rule and rule(model_id.lower()))


def matches_extra(model_id: str, patterns: list[str]) -> bool:
    return any(fnmatch(model_id.lower(), p.lower()) for p in patterns)
