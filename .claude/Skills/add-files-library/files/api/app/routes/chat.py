from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.deps import ChatServiceDep, SettingsDep
from app.library_chat import rag_chat_events
from app.schemas import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


def _check_images(body: ChatRequest, settings: Settings) -> None:
    def reject(message: str) -> None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)

    total = 0
    for m in body.messages:
        if len(m.images) > settings.max_images_per_message:
            reject(f"Up to {settings.max_images_per_message} photos per message")
        for image in m.images:
            if image.size > settings.max_image_bytes:
                limit = settings.max_image_bytes / 1024 / 1024
                reject(f"A photo is {image.size / 1024 / 1024:.1f} MB; the limit is {limit:g} MB")
        total += len(m.images)
    if total > settings.max_images_per_request:
        reject(f"Up to {settings.max_images_per_request} photos per conversation request")


SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post(
    "",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def chat(
    body: ChatRequest, request: Request, service: ChatServiceDep, settings: SettingsDep
) -> StreamingResponse:
    """Stream a reply as server-sent events.

    Events: `meta` (which provider/model answered), unnamed `data: {"delta": ...}`
    chunks, then `done` or `error`. With `rag`, the Library answers and a `sources`
    event (citations, and the text with [n] markers) comes before `done`.
    """
    if len(body.messages) > settings.max_messages:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Too many messages")
    if any(len(m.content) > settings.max_message_chars for m in body.messages):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Message is too long")
    if body.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Last message must be user")
    _check_images(body, settings)

    library = getattr(request.app.state, "library", None)
    use_library = bool(body.rag and (body.rag.collections or body.rag.files))
    stream = rag_chat_events(library, body) if use_library and library else service.stream(body)

    async def events() -> AsyncIterator[str]:
        async for event in stream:
            if await request.is_disconnected():
                break
            yield event.to_sse()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
