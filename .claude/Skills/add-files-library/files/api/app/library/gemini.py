"""`RagEngine` on Gemini File Search: Google chunks, embeds, stores and searches
the documents; Gemini answers with grounding metadata we turn into citations.

Only Gemini models can use a File Search store. Google deletes the raw uploaded
file after 48 hours (the indexed chunks stay), so the Library keeps its own copy
of every original.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import httpx
from google.genai import errors, types

from .citations import answer_from_response
from .engine import (
    NOT_FOUND,
    Delta,
    IndexingError,
    MetadataValue,
    RagError,
    RagEvent,
    StoreInfo,
    Turn,
)

SYSTEM_INSTRUCTION = (
    "You answer questions using only the documents found with the File Search tool. "
    "Be concise and specific: give numbers, dates and conditions exactly as written. "
    "Use Markdown when it helps readability. "
    "If the documents do not contain the answer, reply exactly: " + NOT_FOUND
)


def _api_message(exc: errors.APIError) -> str:
    return f"Gemini API error {exc.code}: {exc.message or exc.status or 'request failed'}"


def _wrap(exc: Exception, prefix: str = "") -> RagError:
    if isinstance(exc, errors.APIError):
        return RagError(prefix + _api_message(exc))
    return RagError(f"{prefix}Can't reach the Gemini API ({exc})")


def _metadata_in(metadata: Mapping[str, MetadataValue]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, value in metadata.items():
        if isinstance(value, bool):
            raise ValueError(f"Metadata {key!r}: booleans aren't supported")
        if isinstance(value, int | float):
            out.append({"key": key, "numeric_value": value})
        elif isinstance(value, list | tuple):
            out.append({"key": key, "string_list_value": {"values": [str(v) for v in value]}})
        else:
            out.append({"key": key, "string_value": str(value)})
    return out


def _contents(turns: Sequence[Turn]) -> list[dict[str, Any]]:
    return [{"role": t.role, "parts": [{"text": t.text}]} for t in turns if t.text.strip()]


class GeminiFileSearchEngine:
    name = "gemini"

    def __init__(
        self,
        client: Any,  # google.genai.Client, or the offline stand-in
        *,
        model: str,
        embedding_model: str = "",
        chunk_tokens: int = 400,
        chunk_overlap: int = 40,
        top_k: int = 6,
        poll_seconds: float = 3.0,
        timeout_seconds: float = 600.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        name: str = "gemini",
    ) -> None:
        self.name = name  # "offline" when driven by the local stand-in
        self.label = "Gemini File Search" if name == "gemini" else "Offline search (testing)"
        self.local = name != "gemini"
        if chunk_overlap >= chunk_tokens:
            raise RagError(
                f"Chunk overlap ({chunk_overlap}) must be smaller than chunk size ({chunk_tokens})"
            )
        self.client = client
        self.model = model
        self.embedding_model = embedding_model
        self.chunk_tokens = chunk_tokens
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._sleep = sleep
        self._clock = clock

    # ------------------------------------------------------------------ stores
    async def ensure_store(self, display_name: str) -> str:
        """The newest store with this display name, created if missing."""

        def run() -> str:
            stores = [
                s for s in self.client.file_search_stores.list() if s.display_name == display_name
            ]
            if stores:
                stores.sort(key=lambda s: str(s.create_time or ""), reverse=True)
                return stores[0].name
            config: dict[str, Any] = {"display_name": display_name}
            if self.embedding_model:
                config["embedding_model"] = self.embedding_model
            return self.client.file_search_stores.create(config=config).name

        try:
            return await asyncio.to_thread(run)
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc

    async def store_info(self, store_id: str) -> StoreInfo | None:
        try:
            s = await asyncio.to_thread(lambda: self.client.file_search_stores.get(name=store_id))
        except errors.ClientError as exc:
            if exc.code == 404:
                return None
            raise _wrap(exc) from exc
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc
        return StoreInfo(
            id=s.name,
            active=int(s.active_documents_count or 0),
            pending=int(s.pending_documents_count or 0),
            failed=int(s.failed_documents_count or 0),
            size_bytes=int(s.size_bytes or 0),
            embedding_model=s.embedding_model,
        )

    # ------------------------------------------------------------------ documents
    async def add_document(
        self,
        store_id: str,
        path: Path,
        *,
        title: str,
        mime_type: str,
        metadata: Mapping[str, MetadataValue],
    ) -> str:
        return await asyncio.to_thread(self._add_sync, store_id, path, title, mime_type, metadata)

    def _add_sync(
        self,
        store_id: str,
        path: Path,
        title: str,
        mime_type: str,
        metadata: Mapping[str, MetadataValue],
    ) -> str:
        config: dict[str, Any] = {
            "display_name": title,
            "mime_type": mime_type,
            "custom_metadata": _metadata_in(metadata),
            "chunking_config": {
                "white_space_config": {
                    "max_tokens_per_chunk": self.chunk_tokens,
                    "max_overlap_tokens": self.chunk_overlap,
                }
            },
        }
        try:
            op = self.client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_id, file=str(path), config=config
            )
            deadline = self._clock() + self.timeout_seconds
            while not op.done:
                if self._clock() >= deadline:
                    raise IndexingError(
                        f"Still indexing after {self.timeout_seconds:.0f} s; try re-indexing later"
                    )
                self._sleep(self.poll_seconds)
                op = self._poll(op)
        except errors.APIError as exc:
            raise IndexingError(_api_message(exc)) from exc
        except (httpx.HTTPError, KeyError, OSError, ValueError) as exc:
            raise IndexingError(f"Upload failed ({exc})") from exc
        if op.error:
            message = op.error.get("message") if isinstance(op.error, dict) else str(op.error)
            raise IndexingError(f"Indexing failed: {message or 'unknown error'}")
        name = op.response.document_name if op.response else None
        if not name:
            raise IndexingError("Indexing finished without a document id")
        return name

    def _poll(self, op: Any, attempts: int = 3) -> Any:
        """One status check; brief network, 429 and 5xx hiccups are retried."""
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                return self.client.operations.get(op)
            except (errors.ServerError, httpx.TransportError) as exc:
                last = exc
            except errors.ClientError as exc:
                if exc.code != 429:
                    raise
                last = exc
            self._sleep(self.poll_seconds * (attempt + 1))
        assert last is not None
        raise last

    async def purge(self, store_id: str, doc_key: str) -> int:
        def run() -> int:
            removed = 0
            for d in self.client.file_search_stores.documents.list(parent=store_id):
                keys = {m.key: m.string_value for m in d.custom_metadata or []}
                if keys.get("doc") == doc_key and d.name:
                    try:
                        self.client.file_search_stores.documents.delete(
                            name=d.name, config={"force": True}
                        )
                        removed += 1
                    except errors.ClientError as exc:
                        if exc.code != 404:
                            raise
            return removed

        try:
            return await asyncio.to_thread(run)
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc

    async def delete_document(self, engine_document_id: str) -> None:
        def run() -> None:
            try:
                self.client.file_search_stores.documents.delete(
                    name=engine_document_id, config={"force": True}
                )
            except errors.ClientError as exc:
                if exc.code != 404:  # already gone is fine
                    raise

        try:
            await asyncio.to_thread(run)
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc

    # ------------------------------------------------------------------ answering
    def _config(self, store_ids: Sequence[str], metadata_filter: str | None) -> Any:
        fs: dict[str, Any] = {"file_search_store_names": list(store_ids)}
        if metadata_filter:
            fs["metadata_filter"] = metadata_filter
        if self.top_k:
            fs["top_k"] = self.top_k
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[types.Tool(file_search=types.FileSearch(**fs))],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    async def stream(
        self, turns: Sequence[Turn], store_ids: Sequence[str], metadata_filter: str | None
    ) -> AsyncIterator[RagEvent]:
        if not turns or turns[-1].role != "user" or not turns[-1].text.strip():
            raise RagError("Ask a question")
        config = self._config(store_ids, metadata_filter)
        contents = _contents(turns)
        aio = getattr(self.client, "aio", None)
        if aio is None:  # offline stand-in: one call, then emit the text in pieces
            try:
                response = await asyncio.to_thread(
                    lambda: self.client.models.generate_content(
                        model=self.model, contents=contents, config=config
                    )
                )
            except (errors.APIError, httpx.HTTPError) as exc:
                raise _wrap(exc) from exc
            answer = answer_from_response(response, self.model)
            words = answer.text.split(" ")
            for i in range(0, len(words), 4):
                yield Delta(" ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else ""))
            yield answer
            return

        text_parts: list[str] = []
        grounding: Any = None
        finish: Any = None
        feedback: Any = None
        try:
            stream = await aio.models.generate_content_stream(
                model=self.model, contents=contents, config=config
            )
            async for chunk in stream:
                feedback = chunk.prompt_feedback or feedback
                cand = chunk.candidates[0] if chunk.candidates else None
                if cand is None:
                    continue
                finish = cand.finish_reason or finish
                grounding = cand.grounding_metadata or grounding
                for part in (cand.content.parts if cand.content else None) or []:
                    if part.text and not part.thought:
                        text_parts.append(part.text)
                        yield Delta(part.text)
        except (errors.APIError, httpx.HTTPError) as exc:
            raise _wrap(exc) from exc
        # Rebuild one response: in a stream, the grounding offsets refer to the whole text.
        full = types.GenerateContentResponse(
            prompt_feedback=feedback,
            candidates=[
                types.Candidate(
                    content=types.Content(
                        role="model", parts=[types.Part(text="".join(text_parts))]
                    )
                    if text_parts
                    else None,
                    grounding_metadata=grounding,
                    finish_reason=finish,
                )
            ]
            if (text_parts or finish)
            else None,
        )
        yield answer_from_response(full, self.model)
