"""An offline stand-in for the parts of `google.genai.Client` that File Search uses.

It lets the whole RAG flow run without a key or network, with the same calls
and the same response *types* as the real API:

- upload extracts text (PDF per page with pypdf, DOCX with python-docx, text
  files as-is) and splits it with the white-space chunker settings you pass;
- operations finish on the second poll, like a short indexing job;
- metadata filters use the same AIP-160 syntax (`key="v" AND (k=1 OR k=2)`);
- "retrieval" is keyword scoring (BM25-like), not embeddings, and the "answer"
  is the best-matching sentences quoted from the retrieved chunks, returned
  with real grounding metadata (chunks + byte-offset supports).

It is a test double for the plumbing, not a model: use a real key to judge
answer quality. Turn it on with RAG_ENGINE=offline (local development, tests).
PDF and DOCX extraction need pypdf and python-docx (dev dependencies).
"""

from __future__ import annotations

import itertools
import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google.genai import types

from .engine import NOT_FOUND

STOP = {
    "a",
    "about",
    "after",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "get",
    "got",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "long",
    "many",
    "much",
    "my",
    "need",
    "of",
    "on",
    "or",
    "our",
    "per",
    "should",
    "the",
    "their",
    "them",
    "there",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "you",
    "your",
}
WORD = re.compile(r"[A-Za-z0-9$][A-Za-z0-9$.,'-]*")


def terms(text: str) -> list[str]:
    out = []
    for w in WORD.findall(text.lower()):
        w = w.strip(".,'-")
        if w and w not in STOP:
            # crude stemming: drop a plural "s", then compare 6-letter prefixes
            out.append((w[:-1] if len(w) > 3 and w.endswith("s") else w)[:6])
    return out


@dataclass
class _Chunk:
    text: str
    page: int | None
    chunk_id: str


@dataclass
class _Doc:
    name: str
    display_name: str
    mime_type: str | None
    size_bytes: int
    metadata: list[dict[str, Any]]
    chunks: list[_Chunk] = field(default_factory=list)

    def meta(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for m in self.metadata:
            if "string_value" in m:
                out[m["key"]] = m["string_value"]
            elif "numeric_value" in m:
                out[m["key"]] = m["numeric_value"]
            elif "string_list_value" in m:
                out[m["key"]] = list(m["string_list_value"]["values"])
        return out


def _extract(path: Path) -> list[tuple[int | None, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return [(i + 1, p.extract_text() or "") for i, p in enumerate(PdfReader(path).pages)]
    if suffix == ".docx":
        from docx import Document

        return [(None, "\n".join(p.text for p in Document(str(path)).paragraphs))]
    return [(None, path.read_text(encoding="utf-8", errors="replace"))]


def _chunk(pages: list[tuple[int | None, str]], size: int, overlap: int) -> list[_Chunk]:
    chunks: list[_Chunk] = []
    for page, text in pages:
        words = text.split()
        step = max(1, size - overlap)
        for start in range(0, len(words), step):
            piece = words[start : start + size]
            if piece:
                chunks.append(_Chunk(" ".join(piece), page, f"c{len(chunks)}"))
            if start + size >= len(words):
                break
    return chunks


# ------------------------------------------------------------------ filter syntax
_CLAUSE = re.compile(r'\s*([A-Za-z0-9_-]+)\s*=\s*("((?:[^"\\]|\\.)*)"|-?\d+(?:\.\d+)?)\s*')


def _match_filter(expr: str | None, meta: dict[str, Any]) -> bool:
    """Evaluates `a AND b AND (c OR d)` where each clause is key="str" or key=number."""
    if not expr:
        return True

    def clause_ok(text: str) -> bool:
        m = _CLAUSE.fullmatch(text)
        if not m:
            raise ValueError(f"Unsupported metadata filter: {text!r}")
        key, raw, string = m.group(1), m.group(2), m.group(3)
        have = meta.get(key)
        if string is not None:
            want = re.sub(r"\\(.)", r"\1", string)
            return have == want or (isinstance(have, list) and want in have)
        return isinstance(have, int | float) and float(have) == float(raw)

    for part in re.split(r"\s+AND\s+", expr.strip()):
        part = part.strip()
        if part.startswith("(") and part.endswith(")"):
            if not any(clause_ok(o) for o in re.split(r"\s+OR\s+", part[1:-1])):
                return False
        elif not clause_ok(part):
            return False
    return True


# ------------------------------------------------------------------ the fake client
class _Operations:
    def __init__(self, owner: OfflineClient) -> None:
        self._owner = owner

    def get(self, operation: Any, *, config: Any = None) -> Any:
        return self._owner._finish(operation)


class _Documents:
    def __init__(self, owner: OfflineClient) -> None:
        self._o = owner

    def _doc(self, name: str) -> _Doc:
        store = name.split("/documents/", maxsplit=1)[0]
        for d in self._o._stores[store]["docs"]:
            if d.name == name:
                return d
        raise KeyError(name)

    def list(self, *, parent: str, config: Any = None) -> list[types.Document]:
        return [self._o._as_document(d) for d in self._o._stores[parent]["docs"]]

    def get(self, *, name: str, config: Any = None) -> types.Document:
        return self._o._as_document(self._doc(name))

    def delete(self, *, name: str, config: Any = None) -> None:
        store = name.split("/documents/", maxsplit=1)[0]
        self._o._stores[store]["docs"] = [
            d for d in self._o._stores[store]["docs"] if d.name != name
        ]


class _Stores:
    def __init__(self, owner: OfflineClient) -> None:
        self._o = owner
        self.documents = _Documents(owner)

    def create(self, *, config: Any = None) -> types.FileSearchStore:
        cfg = dict(config or {})
        name = f"fileSearchStores/offline-{next(self._o._ids)}"
        self._o._stores[name] = {"display_name": cfg.get("display_name"), "docs": []}
        return types.FileSearchStore(name=name, display_name=cfg.get("display_name"))

    def list(self, *, config: Any = None) -> list[types.FileSearchStore]:
        return [
            types.FileSearchStore(name=n, display_name=s["display_name"])
            for n, s in self._o._stores.items()
        ]

    def get(self, *, name: str, config: Any = None) -> types.FileSearchStore:
        s = self._o._stores[name]
        return types.FileSearchStore(
            name=name,
            display_name=s["display_name"],
            active_documents_count=len(s["docs"]),
            pending_documents_count=0,
            failed_documents_count=0,
            size_bytes=sum(d.size_bytes for d in s["docs"]),
            embedding_model="offline-keyword-search",
        )

    def delete(self, *, name: str, config: Any = None) -> None:
        self._o._stores.pop(name, None)

    def upload_to_file_search_store(
        self, *, file_search_store_name: str, file: str, config: Any = None
    ) -> types.UploadToFileSearchStoreOperation:
        cfg = dict(config or {})
        self._o.uploads.append({"store": file_search_store_name, "file": file, "config": cfg})
        ws = (cfg.get("chunking_config") or {}).get("white_space_config") or {}
        path = Path(file)
        doc_id = re.sub(r"[^a-z0-9]+", "", path.stem.lower())[:30] + f"-{next(self._o._ids)}"
        doc = _Doc(
            name=f"{file_search_store_name}/documents/{doc_id}",
            display_name=cfg.get("display_name") or path.name,
            mime_type=cfg.get("mime_type"),
            size_bytes=path.stat().st_size,
            metadata=list(cfg.get("custom_metadata") or []),
        )
        doc.chunks = _chunk(
            _extract(path), ws.get("max_tokens_per_chunk", 400), ws.get("max_overlap_tokens", 40)
        )
        op_name = f"{file_search_store_name}/operations/op{next(self._o._ids)}"
        self._o._pending[op_name] = (file_search_store_name, doc)
        return types.UploadToFileSearchStoreOperation(name=op_name, done=False)


class _Models:
    def __init__(self, owner: OfflineClient) -> None:
        self._o = owner

    def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self._o.requests.append({"model": model, "contents": contents, "config": config})
        fs = config.tools[0].file_search
        if isinstance(contents, list):  # [{"role", "parts": [{"text"}]}]: answer the last turn
            last = contents[-1]
            contents = " ".join(p.get("text", "") for p in last.get("parts", []))
        return self._o._answer(
            str(contents), fs.file_search_store_names, fs.metadata_filter, fs.top_k or 5
        )


class OfflineClient:
    """Drop-in for `google.genai.Client` in GeminiFileSearchEngine (offline)."""

    def __init__(self) -> None:
        self._ids = itertools.count(1)
        self._stores: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, tuple[str, _Doc]] = {}
        self.uploads: list[dict[str, Any]] = []  # what the engine sent, for tests
        self.requests: list[dict[str, Any]] = []
        self.file_search_stores = _Stores(self)
        self.operations = _Operations(self)
        self.models = _Models(self)

    # indexing finishes on the first poll after upload
    def _finish(self, op: types.UploadToFileSearchStoreOperation) -> Any:
        store, doc = self._pending.pop(op.name, (None, None))
        if doc is None:
            return op
        if not doc.chunks:
            return types.UploadToFileSearchStoreOperation(
                name=op.name, done=True, error={"code": 3, "message": "No text could be extracted"}
            )
        self._stores[store]["docs"].append(doc)
        return types.UploadToFileSearchStoreOperation(
            name=op.name,
            done=True,
            response=types.UploadToFileSearchStoreResponse(parent=store, document_name=doc.name),
        )

    def _as_document(self, d: _Doc) -> types.Document:
        return types.Document.model_validate(
            {
                "name": d.name,
                "display_name": d.display_name,
                "state": "STATE_ACTIVE",
                "size_bytes": d.size_bytes,
                "mime_type": d.mime_type,
                "custom_metadata": d.metadata,
            }
        )

    def _answer(
        self, question: str, stores: Iterable[str], flt: str | None, top_k: int
    ) -> types.GenerateContentResponse:
        q = set(terms(question))
        pool: list[tuple[_Doc, _Chunk]] = [
            (d, c)
            for s in stores
            for d in self._stores.get(s, {}).get("docs", [])
            if _match_filter(flt, d.meta())
            for c in d.chunks
        ]
        n = max(1, len(pool))
        df = Counter(t for _, c in pool for t in set(terms(c.text)))

        def score(text: str) -> float:
            tf = Counter(terms(text))
            return sum((1 + math.log(tf[t])) * math.log(1 + n / df.get(t, n)) for t in q if tf[t])

        ranked = sorted(pool, key=lambda dc: score(dc[1].text), reverse=True)[:top_k]
        ranked = [dc for dc in ranked if score(dc[1].text) > 0]

        # Greedily pick up to 2 sentences that cover the most question terms.
        candidates: list[tuple[str, int, set[str]]] = []
        for i, (_, c) in enumerate(ranked):
            # Sentences, or lines (headings, list items), without Markdown markers.
            for raw in re.split(r"(?<=[.!?])\s+|\n+|\s+(?=#+\s)", c.text):
                sent = re.sub(r"^\s*(?:#+|[-*]|\d+[.)])\s+", "", raw).strip()
                covers = q & set(terms(sent))
                if covers and len(sent) > 3:
                    candidates.append((sent, i, covers))
        chosen: list[tuple[float, str, int]] = []
        covered: set[str] = set()
        for _ in range(2):
            pick = max(candidates, key=lambda c: (len(c[2] - covered), score(c[0])), default=None)
            if pick is None or not (pick[2] - covered):
                break
            if not chosen and len(pick[2]) < min(2, len(q)):
                break  # not even one sentence matches the question well: refuse
            chosen.append((0.0, pick[0], pick[1]))
            covered |= pick[2]
            candidates.remove(pick)
        if not chosen:
            return types.GenerateContentResponse.model_validate(
                {"candidates": [{"content": {"role": "model", "parts": [{"text": NOT_FOUND}]}}]}
            )
        text, supports, offset = "", [], 0
        for k, (_, sent, idx) in enumerate(chosen):
            piece = (" " if k else "") + sent
            start = offset + (1 if k else 0)
            offset += len(piece.encode("utf-8"))
            text += piece
            supports.append(
                {
                    "segment": {
                        "part_index": 0,
                        "start_index": start,
                        "end_index": offset,
                        "text": sent,
                    },
                    "grounding_chunk_indices": [idx],
                }
            )
        chunks = [
            {
                "retrieved_context": {
                    "title": d.display_name,
                    "text": c.text,
                    "document_name": d.name,
                    "page_number": c.page,
                    "custom_metadata": d.metadata,
                }
            }
            for d, c in ranked
        ]
        return types.GenerateContentResponse.model_validate(
            {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": text}]},
                        "grounding_metadata": {
                            "grounding_chunks": chunks,
                            "grounding_supports": supports,
                            "retrieval_queries": [question],
                        },
                    }
                ]
            }
        )
