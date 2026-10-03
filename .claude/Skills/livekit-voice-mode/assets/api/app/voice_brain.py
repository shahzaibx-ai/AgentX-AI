"""Connects voice mode to this app's chat pipeline.

Voice replies go through the same ChatService as text chat: the model picked
in the dropdown, Ollama first, cloud fallback, the same `meta` event.
"""

from collections.abc import AsyncIterator

from fastapi import Request

from app.schemas import ChatMessage, ChatRequest
from app.services.chat import ChatService
from app.voice import BrainEvent, BrainRequest


async def chat_brain(request: Request, req: BrainRequest) -> AsyncIterator[BrainEvent]:
    settings = request.app.state.settings
    service = ChatService(
        request.app.state.registry, settings.system_prompt, settings.allow_cloud_fallback
    )
    chat_request = ChatRequest(
        messages=[ChatMessage(**m) for m in req.messages],
        provider=req.provider,
        model=req.model,
        temperature=req.temperature,
    )
    async for event in service.stream(chat_request):
        yield event.type, event.data
