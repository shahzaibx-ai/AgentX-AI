"""Adapts the Library's answer stream to the chat route's server-sent events.

A chat request with `rag` (collections and/or chat files) is answered by the
Library's engine instead of the model picker's choice, because File Search
only works with Gemini. The `meta` event says so; a `sources` event at the end
carries the numbered citations and the answer text with [n] markers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.library import Answer, LibraryService, RagError, Turn
from app.schemas import ChatMessage, ChatRequest
from app.services.chat import ChatEvent


def to_turns(messages: list[ChatMessage]) -> list[Turn]:
    turns: list[Turn] = []
    for m in messages:
        if m.role == "system":
            continue
        text = m.content.strip()
        if m.images:
            n = len(m.images)
            note = f"[Shared {'a photo' if n == 1 else f'{n} photos'}]"
            text = f"{note}\n{text}".strip()
        if not text:
            continue
        role = "user" if m.role == "user" else "model"
        if turns and turns[-1].role == role:  # Gemini wants alternating turns
            turns[-1] = Turn(role, f"{turns[-1].text}\n\n{text}")
        else:
            turns.append(Turn(role, text))
    while turns and turns[0].role != "user":
        turns.pop(0)
    return turns


async def rag_chat_events(
    library: LibraryService, request: ChatRequest
) -> AsyncIterator[ChatEvent]:
    scope = request.rag
    assert scope is not None
    engine = library.engine
    if engine is None:
        yield ChatEvent(
            "error",
            {
                "message": "Files and the Library are off. Set GEMINI_API_KEY in the API's .env "
                "(or RAG_ENGINE=offline for local testing)."
            },
        )
        return
    # Another model was picked in the menu: say which one answers instead (a Gemini
    # chat model is close enough when the engine is Gemini).
    same_family = engine.name == "gemini" and request.provider == "gemini"
    picked = (
        request.model
        if request.provider and request.model != engine.model and not same_family
        else None
    )
    notice = (
        f"Searching files and the Library uses {engine.label}, so {engine.model} answered "
        f"instead of {picked}."
        if picked
        else None
    )
    turns = to_turns(request.messages)
    started = False
    try:
        flt, skipped = library.resolve_scope(scope.collections, scope.files, scope.chat_id)
        if skipped:
            gone = (
                "1 earlier file in this chat is no longer available"
                if skipped == 1
                else f"{skipped} earlier files in this chat are no longer available"
            )
            notice = f"{notice} {gone}." if notice else f"{gone[0].upper()}{gone[1:]}."
        async for event in library.answer_stream(turns, flt):
            if not started:
                started = True
                yield ChatEvent(
                    "meta",
                    {
                        "provider": engine.name,
                        "provider_label": engine.label,
                        "model": engine.model,
                        "local": engine.local,
                        "fallback": False,  # a note, not a failure: see `notice`
                        "notice": notice,
                    },
                )
            if isinstance(event, tuple):
                answer, sources = event
                assert isinstance(answer, Answer)
                yield ChatEvent(
                    "sources",
                    {
                        "cited_text": answer.cited_text,
                        "grounded": answer.grounded,
                        "sources": [s.__dict__ for s in sources] if answer.grounded else [],
                    },
                )
            else:
                yield ChatEvent("delta", {"delta": event.text})
    except RagError as exc:
        yield ChatEvent("error", {"message": str(exc)})
        return
    yield ChatEvent("done", {})
