"""The Library: files, collections, indexing and answering with citations.

    upload ─► original saved under LIBRARY_DATA_DIR/files ─► record (queued)
           ─► indexing worker ─► engine.add_document(scope metadata) ─► indexed | failed
    question + collections/files ─► filter built here (never by the client)
           ─► engine.stream ─► deltas … answer with numbered sources

Every document carries metadata `scope` ("c:<collection id>" or "chat:<chat id>")
and `doc` (its id), so one search store serves the whole app and each question
only sees what it was given.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

from .db import Collection, Document, LibraryDB, new_id
from .engine import Answer, Delta, IndexingError, RagEngine, RagError, Turn, ask
from .settings import LibrarySettings

logger = logging.getLogger(__name__)

# Types File Search reads, with the MIME type sent for each (set explicitly: the OS
# guesses wrong or not at all for some, e.g. ".ts" or ".go").
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".rtf": "application/rtf",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".json": "application/json",
    ".xml": "application/xml",
    **dict.fromkeys(
        [
            ".yaml",
            ".yml",
            ".sql",
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".java",
            ".go",
            ".rs",
            ".c",
            ".cpp",
            ".h",
            ".cs",
            ".rb",
            ".php",
            ".sh",
            ".kt",
            ".swift",
            ".log",
        ],
        "text/plain",
    ),
}
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
CHUNK = 1024 * 1024


class UploadError(RagError):
    """The upload can't be accepted (type, size, empty, duplicate)."""

    def __init__(self, message: str, status: int = 422, existing: Document | None = None):
        super().__init__(message)
        self.status = status
        self.existing = existing


def fmt_mb(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, round(n / 1024))} KB"


def type_problem(filename: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext in PHOTO_EXTS:
        return f"{filename} is a photo. Use Add photos for images."
    if ext not in MIME_TYPES:
        kind = f"{ext} files" if ext else "Files without a type"
        return (
            f"{kind} can't be read. Use PDF, Word, Excel, PowerPoint, text, CSV, "
            "Markdown, HTML, JSON or code."
        )
    return None


def scope_of(doc: Document) -> str:
    return f"c:{doc.collection_id}" if doc.kind == "library" else f"chat:{doc.chat_id}"


def _lit(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_scope_filter(collection_ids: Sequence[str], document_ids: Sequence[str]) -> str:
    """Only these collections and these documents: `(scope="c:a" OR doc="d1")`."""
    clauses = [f"scope={_lit('c:' + c)}" for c in collection_ids]
    clauses += [f"doc={_lit(d)}" for d in document_ids]
    if not clauses:
        raise RagError("Nothing to search: pick a collection or add a file")
    return clauses[0] if len(clauses) == 1 else "(" + " OR ".join(clauses) + ")"


@dataclass
class SourceOut:
    number: int
    title: str
    text: str
    page: int | None
    cited: bool
    document_id: str | None
    kind: str | None
    collection: str | None


class LibraryService:
    def __init__(
        self, settings: LibrarySettings, engine: RagEngine | None, problem: str | None = None
    ) -> None:
        self.settings = settings
        self.engine = engine
        self.problem = problem  # why the Library is off although it was configured
        self.data_dir = Path(settings.library_data_dir)
        self.files_dir = self.data_dir / "files"
        self._db: LibraryDB | None = None  # opened on first use, not at import time
        self._store_id: str | None = None
        self._store_lock = asyncio.Lock()
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: list[asyncio.Task[None]] = []
        self._active: set[str] = set()
        self._interrupted: set[str] = set()  # uploads cut off by a restart: purge first

    # ------------------------------------------------------------------ lifecycle
    @property
    def db(self) -> LibraryDB:
        if self._db is None:
            self.files_dir.mkdir(parents=True, exist_ok=True)
            self._db = LibraryDB(self.data_dir / "library.db")
        return self._db

    @property
    def enabled(self) -> bool:
        return self.engine is not None

    def disable(self, problem: str) -> None:
        self.engine = None
        self.problem = problem

    async def start(self) -> None:
        if not self.engine:
            return
        for doc in self.db.unfinished_documents():  # resume after a restart
            if doc.status == "processing":
                self._interrupted.add(doc.id)
            self.db.update_document(doc.id, status="queued", step="Waiting to be indexed")
            self._queue.put_nowait(doc.id)
        # Indexed by another engine (e.g. after switching to a new pipeline): re-index.
        indexed, _ = self.db.list_documents(status="indexed", limit=100_000)
        for doc in indexed:
            if doc.engine and doc.engine != self.engine.name:
                self.db.update_document(doc.id, status="queued", step="Re-indexing for new engine")
                self._queue.put_nowait(doc.id)
        for _ in range(self.settings.rag_index_concurrency):
            self._tasks.append(asyncio.create_task(self._worker()))
        if self.settings.chat_file_retention_days:
            self._tasks.append(asyncio.create_task(self._retention_loop()))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self._tasks.clear()
        if self._db is not None:
            self._db.close()
            self._db = None

    async def store_id(self) -> str:
        assert self.engine
        if self._store_id:
            return self._store_id
        async with self._store_lock:
            if not self._store_id:
                self._store_id = await self.engine.ensure_store(self.settings.rag_store_name)
                self.db.set_kv(f"store:{self.engine.name}", self._store_id)
        return self._store_id

    def _require(self) -> RagEngine:
        if not self.engine:
            raise RagError(
                "Files and the Library are off. Set GEMINI_API_KEY in the API's .env "
                "(or RAG_ENGINE=offline for local testing)."
            )
        return self.engine

    def queue_size(self) -> int:
        return self._queue.qsize() + len(self._active)

    # ------------------------------------------------------------------ collections
    def collections(self) -> list[Collection]:
        return self.db.list_collections()

    def create_collection(self, name: str, description: str, actor: str) -> Collection:
        name = name.strip()
        if not name:
            raise UploadError("Give the collection a name")
        if self.db.collection_by_name(name):
            raise UploadError(f"A collection called {name} already exists", 409)
        c = self.db.create_collection(name, description.strip())
        self.db.log(actor, f"created the collection {name}")
        return c

    def update_collection(self, cid: str, name: str, description: str, actor: str) -> Collection:
        c = self.db.get_collection(cid)
        if not c:
            raise UploadError("Collection not found", 404)
        other = self.db.collection_by_name(name.strip())
        if other and other.id != cid:
            raise UploadError(f"A collection called {name} already exists", 409)
        self.db.update_collection(cid, name.strip() or c.name, description.strip())
        self.db.log(actor, f"renamed or described the collection {name}")
        result = self.db.get_collection(cid)
        assert result
        return result

    async def delete_collection(self, cid: str, actor: str) -> int:
        c = self.db.get_collection(cid)
        if not c:
            raise UploadError("Collection not found", 404)
        docs, _ = self.db.list_documents(collection_id=cid)
        for d in docs:
            await self.delete_document(d.id, actor, log=False)
        self.db.delete_collection(cid)
        self.db.log(actor, f"deleted the collection {c.name} and its {len(docs)} documents")
        return len(docs)

    # ------------------------------------------------------------------ uploads
    async def add_file(
        self,
        stream: BinaryIO,
        filename: str,
        *,
        kind: str,
        collection_id: str | None = None,
        chat_id: str | None = None,
        actor: str,
        replace: bool = False,
    ) -> Document:
        self._require()
        filename = Path(filename or "file").name[:200] or "file"
        if problem := type_problem(filename):
            raise UploadError(problem, 415)
        limit = (
            self.settings.library_file_max_bytes
            if kind == "library"
            else self.settings.chat_file_max_bytes
        )
        if kind == "library" and not (collection_id and self.db.get_collection(collection_id)):
            raise UploadError("Pick a collection for this document", 404)
        if kind == "chat" and not chat_id:
            raise UploadError("Missing chat id")

        ext = Path(filename).suffix.lower()
        doc_id = new_id()
        tmp = self.files_dir / f".{doc_id}.part"
        digest, size = hashlib.sha256(), 0
        try:
            with tmp.open("wb") as out:
                while chunk := await asyncio.to_thread(stream.read, CHUNK):
                    size += len(chunk)
                    if size > limit:
                        raise UploadError(
                            f"{filename} is over the {fmt_mb(limit)} limit. Split it or export "
                            "a smaller copy.",
                            413,
                        )
                    digest.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise UploadError(f"{filename} is empty")
            sha = digest.hexdigest()
            dup = self.db.find_duplicate(kind, sha, collection_id if kind == "library" else chat_id)
            if dup and kind == "chat":
                # The same file added twice in one chat: reuse it. The route tells the
                # client (`reused`), so removing the new chip keeps the earlier copy.
                return dup
            if dup and not replace:
                raise UploadError(
                    f"{filename} is already in this collection as {dup.title}", 409, existing=dup
                )
            if dup:
                try:
                    await self.delete_document(dup.id, actor, log=False)
                except RagError as exc:
                    raise UploadError(f"Couldn't replace {dup.title}: {exc}", 502) from exc
            final = self.files_dir / f"{doc_id}{ext}"
            os.replace(tmp, final)
        finally:
            tmp.unlink(missing_ok=True)

        doc = self.db.insert_document(
            id=doc_id,
            kind=kind,
            collection_id=collection_id if kind == "library" else None,
            chat_id=chat_id if kind == "chat" else None,
            title=filename,
            filename=filename,
            ext=ext,
            mime=MIME_TYPES[ext],
            size=size,
            sha256=sha,
            uploaded_by=actor,
        )
        if kind == "library":
            coll = self.db.get_collection(collection_id or "")
            self.db.log(
                actor,
                f"{'replaced' if dup else 'uploaded'} {filename} in {coll.name if coll else '?'}",
            )
        self._queue.put_nowait(doc.id)
        return doc

    def file_path(self, doc: Document) -> Path:
        return self.files_dir / f"{doc.id}{doc.ext}"

    async def reindex(self, document_id: str, actor: str) -> Document:
        self._require()
        doc = self.db.get_document(document_id)
        if not doc:
            raise UploadError("Document not found", 404)
        if doc.status in {"queued", "processing"}:
            raise UploadError(f"{doc.title} is already being indexed", 409)
        if not self.file_path(doc).exists():
            raise UploadError(f"The original of {doc.title} is missing; upload it again", 410)
        self.db.update_document(doc.id, status="queued", step="Waiting to be indexed", error="")
        self.db.log(actor, f"re-indexed {doc.title}")
        self._queue.put_nowait(doc.id)
        result = self.db.get_document(doc.id)
        assert result
        return result

    async def delete_document(self, document_id: str, actor: str, *, log: bool = True) -> None:
        doc = self.db.get_document(document_id)
        if not doc:
            raise UploadError("Document not found", 404)
        if doc.engine_doc_id and self.engine and doc.engine == self.engine.name:
            await self.engine.delete_document(doc.engine_doc_id)
        self.db.delete_document(doc.id)  # a worker that finishes later sees it's gone
        self.file_path(doc).unlink(missing_ok=True)
        if log and doc.kind == "library":
            self.db.log(actor, f"deleted {doc.title}")

    # ------------------------------------------------------------------ indexing worker
    async def _worker(self) -> None:
        while True:
            doc_id = await self._queue.get()
            self._active.add(doc_id)
            try:
                await self._index(doc_id)
            except Exception:  # never let one document stop the worker
                logger.exception("Indexing %s crashed", doc_id)
                self.db.update_document(
                    doc_id, status="failed", step="", error="Unexpected error while indexing"
                )
            finally:
                self._active.discard(doc_id)
                self._queue.task_done()

    async def drain(self) -> None:
        """Wait until the queue is empty (tests and scripts)."""
        await self._queue.join()

    async def _index(self, doc_id: str) -> None:
        engine = self._require()
        doc = self.db.get_document(doc_id)
        if not doc or doc.status not in {"queued", "processing"}:
            return
        self.db.update_document(doc.id, status="processing", step="Uploading and indexing")
        old = doc.engine_doc_id if doc.engine == engine.name else ""
        try:
            if old:
                await engine.delete_document(old)
            store = await self.store_id()
            if doc.id in self._interrupted:
                self._interrupted.discard(doc.id)
                await engine.purge(store, doc.id)
            engine_doc = await engine.add_document(
                store,
                self.file_path(doc),
                title=doc.title,
                mime_type=doc.mime,
                metadata={"scope": scope_of(doc), "doc": doc.id},
            )
        except (IndexingError, RagError) as exc:
            # A timed-out upload may still finish on the service: don't leave a copy that
            # answers would keep citing.
            with contextlib.suppress(RagError):
                await engine.purge(await self.store_id(), doc.id)
            if self.db.get_document(doc.id):
                self.db.update_document(
                    doc.id, status="failed", step="", error=str(exc), engine_doc_id=""
                )
                if doc.kind == "library":
                    self.db.log("System", f"could not index {doc.title}: {exc}")
            return
        if not self.db.get_document(doc.id):  # deleted while indexing
            await engine.delete_document(engine_doc)
            return
        self.db.update_document(
            doc.id,
            status="indexed",
            step="",
            error="",
            engine=engine.name,
            engine_doc_id=engine_doc,
            indexed_at=time.time(),
        )

    # ------------------------------------------------------------------ retention
    async def _retention_loop(self) -> None:
        while True:
            try:
                removed = await self.sweep_chat_files()
                if removed:
                    self.db.log("System", f"deleted {removed} chat files past the retention time")
            except Exception:
                logger.exception("Chat file clean-up failed")
            await asyncio.sleep(3600)

    async def sweep_chat_files(self, now: float | None = None) -> int:
        days = self.settings.chat_file_retention_days
        if not days:
            return 0
        cutoff = (now or time.time()) - days * 86400
        expired = self.db.expired_chat_documents(cutoff)
        for d in expired:
            with contextlib.suppress(RagError):
                await self.delete_document(d.id, "System", log=False)
        return len(expired)

    # ------------------------------------------------------------------ answering
    def _check_scope(
        self,
        collection_ids: Sequence[str],
        file_ids: Sequence[str],
        chat_id: str | None = None,
    ) -> tuple[list[str], list[Document], int]:
        """Collections must exist. Files are this chat's files: ones deleted or expired
        since they were sent are skipped (the count is returned), so an old file doesn't
        break the chat. Ids that aren't chat files of this chat are skipped too."""
        names = []
        for cid in collection_ids:
            c = self.db.get_collection(cid)
            if not c:
                raise RagError("A collection you picked no longer exists. Pick another one.")
            names.append(c.name)
        files, skipped = [], 0
        for fid in dict.fromkeys(file_ids):
            d = self.db.get_document(fid)
            if not d or d.kind != "chat" or (chat_id and d.chat_id != chat_id):
                skipped += 1
                continue
            if d.status in {"queued", "processing"}:
                raise RagError(f"{d.title} is still being indexed. Try again in a moment.")
            if d.status == "failed":
                raise RagError(f"{d.title} couldn't be indexed: {d.error}")
            files.append(d)
        if not names and not files and file_ids:
            days = self.settings.chat_file_retention_days
            raise RagError(
                "The files in this chat are no longer available"
                + (f" (files are kept {days} days after they were last used)" if days else "")
                + ". Add them again to ask about them."
            )
        return names, files, skipped

    def resolve_scope(
        self, collection_ids: Sequence[str], file_ids: Sequence[str], chat_id: str | None = None
    ) -> tuple[str, int]:
        """The metadata filter for a question, and how many old files were skipped."""
        _, files, skipped = self._check_scope(collection_ids, file_ids, chat_id)
        return build_scope_filter(collection_ids, [f.id for f in files]), skipped

    def _sources(self, answer: Answer) -> list[SourceOut]:
        mine = self.db.documents_by_engine_ids(s.engine_document_id or "" for s in answer.sources)
        colls = {c.id: c.name for c in self.db.list_collections()}
        out = []
        for s in answer.sources:
            d = mine.get(s.engine_document_id or "") or (
                self.db.get_document(s.doc_key) if s.doc_key else None
            )
            out.append(
                SourceOut(
                    number=s.number,
                    title=d.title if d else s.title,
                    text=s.text,
                    page=s.page,
                    cited=s.cited,
                    document_id=d.id if d else None,
                    kind=d.kind if d else None,
                    collection=colls.get(d.collection_id or "") if d else None,
                )
            )
        used = [o.document_id for o in out if o.document_id and o.cited]
        self.db.mark_used(used)
        return out

    async def answer_stream(
        self, turns: Sequence[Turn], metadata_filter: str
    ) -> AsyncIterator[Delta | tuple[Answer, list[SourceOut]]]:
        """Deltas, then (answer, sources). Raises RagError with a readable message.
        Get the filter from `resolve_scope`."""
        engine = self._require()
        flt = metadata_filter
        store = await self.store_id()
        self.db.count_search(datetime.now(UTC).date().isoformat())
        async for event in engine.stream(turns, [store], flt):
            if isinstance(event, Answer):
                yield event, self._sources(event)
            else:
                yield event

    async def test_question(
        self, question: str, collection_ids: Sequence[str]
    ) -> tuple[Answer, list[SourceOut], float]:
        engine = self._require()
        if not question.strip():
            raise RagError("Type a question")
        ids = list(collection_ids) or [c.id for c in self.db.list_collections()]
        flt, _ = self.resolve_scope(ids, [])
        start = time.perf_counter()
        answer = await ask(engine, [Turn("user", question.strip())], [await self.store_id()], flt)
        return answer, self._sources(answer), time.perf_counter() - start

    # ------------------------------------------------------------------ overview
    async def overview(self) -> dict[str, Any]:
        totals = self.db.totals()
        today = datetime.now(UTC).date()
        days = [(today - timedelta(days=13 - i)).isoformat() for i in range(14)]
        store = None
        store_error = None
        if self.engine:
            try:
                info = await self.engine.store_info(await self.store_id())
                store = info.__dict__ if info else None
            except RagError as exc:
                store_error = str(exc)
        return {
            "totals": totals,
            "searches": self.db.searches(days),
            "queue": self.queue_size(),
            "store": store,
            "store_error": store_error,
            "activity": self.db.recent_activity(),
        }
