"""The contract every RAG backend implements, plus shared helpers.

The Library service, the chat route and the tests only see these types. Today
`GeminiFileSearchEngine` implements it; the next step, a LangChain/LangGraph
pipeline with Ollama embeddings and pgvector/Qdrant, implements the same
methods so the rest of the app doesn't change.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

NOT_FOUND = "I couldn't find that in the documents."
RIGHT_QUOTE = chr(0x2019)  # models sometimes write a curly apostrophe

MetadataValue = str | int | float | Sequence[str]


class RagError(Exception):
    """A failure whose message is safe to show to people."""


class IndexingError(RagError):
    """A document could not be indexed."""


def is_not_found(text: str) -> bool:
    """The answer is the refusal sentence (tolerates curly quotes, case, spacing)."""
    norm = " ".join(text.replace(RIGHT_QUOTE, "'").lower().split()).rstrip(".")
    return norm.startswith(NOT_FOUND.lower().rstrip("."))


@dataclass(frozen=True)
class Turn:
    role: Literal["user", "model"]
    text: str


@dataclass(frozen=True)
class Source:
    number: int  # [n] in the answer
    title: str
    text: str  # the retrieved passage
    page: int | None = None
    engine_document_id: str | None = None
    doc_key: str | None = None  # our document id, from the chunk's `doc` metadata
    cited: bool = True  # False: retrieved but not linked to a sentence


@dataclass(frozen=True)
class Answer:
    text: str
    cited_text: str  # text with [n] markers
    sources: list[Source]
    model: str
    grounded: bool
    retrieval_queries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StoreInfo:
    id: str
    active: int = 0
    pending: int = 0
    failed: int = 0
    size_bytes: int = 0
    embedding_model: str | None = None


@dataclass(frozen=True)
class Delta:
    text: str


RagEvent = Delta | Answer


class RagEngine(Protocol):
    name: str  # "gemini", "offline", later "langgraph"
    label: str  # shown to people: "Gemini File Search", "Offline search (testing)", …
    local: bool  # True when nothing leaves your servers (offline, self-hosted)
    model: str

    async def ensure_store(self, display_name: str) -> str: ...

    async def store_info(self, store_id: str) -> StoreInfo | None: ...

    async def add_document(
        self,
        store_id: str,
        path: Path,
        *,
        title: str,
        mime_type: str,
        metadata: Mapping[str, MetadataValue],
    ) -> str: ...  # returns the engine's document id

    async def delete_document(self, engine_document_id: str) -> None: ...

    async def purge(self, store_id: str, doc_key: str) -> int:
        """Delete every copy of our document `doc_key` (its `doc` metadata) in the store:
        copies left by an upload that timed out or was cut off by a restart."""
        ...

    def stream(
        self, turns: Sequence[Turn], store_ids: Sequence[str], metadata_filter: str | None
    ) -> AsyncIterator[RagEvent]: ...  # Delta*, then exactly one Answer


async def ask(
    engine: RagEngine, turns: Sequence[Turn], store_ids: Sequence[str], metadata_filter: str | None
) -> Answer:
    """Non-streaming helper over `stream`."""
    async for event in engine.stream(turns, store_ids, metadata_filter):
        if isinstance(event, Answer):
            return event
    raise RagError("The search engine returned no answer")


# ------------------------------------------------------------------ metadata filters
def _literal(value: str | int | float) -> str:
    if isinstance(value, bool):
        raise TypeError("Booleans are not supported in metadata filters")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Numbers in filters must be finite")
        return f"{value:.10f}".rstrip("0").rstrip(".")
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_filter(where: Mapping[str, MetadataValue] | None) -> str | None:
    """`{"scope": ["c:hr", "chat:1"], "year": 2026}` →
    `(scope="c:hr" OR scope="chat:1") AND year=2026` (AIP-160 syntax)."""
    if not where:
        return None
    clauses: list[str] = []
    for key, value in where.items():
        if not key or not key[0].isalpha() or not key.replace("_", "").isalnum():
            raise ValueError(f"Invalid metadata key: {key!r}")
        if isinstance(value, list | tuple | set | frozenset):
            options = [f"{key}={_literal(v)}" for v in value]
            if not options:
                raise ValueError(f"Empty list for metadata key {key!r}")
            clauses.append(options[0] if len(options) == 1 else f"({' OR '.join(options)})")
        else:
            clauses.append(f"{key}={_literal(value)}")
    return " AND ".join(clauses)
