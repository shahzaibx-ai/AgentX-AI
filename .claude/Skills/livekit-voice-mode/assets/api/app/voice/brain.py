"""The contract between voice mode and the host app's chat pipeline."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Request

BrainEventName = Literal["meta", "delta", "error", "done"]
BrainEvent = tuple[BrainEventName, dict[str, Any]]


@dataclass(frozen=True)
class BrainRequest:
    """What the voice agent needs answered.

    `messages` are plain {"role": "system" | "user" | "assistant", "content": str}
    dicts: one system message first (the agent's instructions), then earlier chat
    history, then the spoken turns; always ending with a user turn.
    `provider` / `model` are what the user picked in the app (None = automatic).
    """

    messages: list[dict[str, str]]
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None


# A brain streams the reply as events:
#   ("meta",  {"provider", "provider_label", "model", "local", "fallback", "notice"})  optional
#   ("delta", {"delta": "text chunk"})                                                   repeated
#   ("error", {"message": "user-safe reason"})   or   ("done", {})                       last
Brain = Callable[[Request, BrainRequest], AsyncIterator[BrainEvent]]
