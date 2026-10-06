"""HTTP API for files in chat (anyone) and the Library (owner only)."""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .db import Collection, Document
from .engine import RagError
from .service import MIME_TYPES, LibraryService, UploadError
from .settings import LibrarySettings

ID = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


# ------------------------------------------------------------------ response models
class CollectionOut(BaseModel):
    id: str
    name: str
    description: str
    documents: int
    size: int
    created_at: float
    updated_at: float


class DocumentOut(BaseModel):
    id: str
    kind: Literal["library", "chat"]
    title: str
    filename: str
    ext: str
    mime: str
    size: int
    status: Literal["queued", "processing", "indexed", "failed"]
    step: str
    error: str
    collection_id: str | None
    collection: str | None = None
    chat_id: str | None
    uploaded_by: str
    uses: int
    engine: str
    created_at: float
    updated_at: float
    indexed_at: float | None
    expires_at: float | None = None
    # Upload only: the same file was already in this chat, and this is that copy.
    reused: bool = False


class LimitsOut(BaseModel):
    chat_file_max_bytes: int
    chat_files_per_message: int
    library_file_max_bytes: int
    chat_file_retention_days: int
    extensions: list[str]


class ConfigOut(BaseModel):
    enabled: bool
    reason: str | None
    engine: str
    label: str  # e.g. "Gemini File Search"
    local: bool  # nothing leaves your servers
    model: str
    owner_auth: Literal["open", "token", "disabled"]
    limits: LimitsOut
    collections: list[CollectionOut]


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)


class BulkIn(BaseModel):
    action: Literal["delete", "reindex", "move"]
    ids: list[ID] = Field(min_length=1, max_length=500)
    collection_id: ID | None = None


class TestIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    collection_ids: list[ID] = Field(default_factory=list, max_length=50)


def _coll(c: Collection) -> CollectionOut:
    return CollectionOut(**c.__dict__)


class LibraryRoutes:
    def __init__(self, service: LibraryService, settings: LibrarySettings, production: bool):
        self.service = service
        self.settings = settings
        self.production = production

    # -------------------------------------------------------------- helpers
    @property
    def owner_auth(self) -> Literal["open", "token", "disabled"]:
        token = (
            self.settings.library_token.get_secret_value() if self.settings.library_token else ""
        )
        if token:
            return "token"
        return "disabled" if self.production else "open"

    def require_owner(self, authorization: str | None = Header(default=None)) -> str:
        mode = self.owner_auth
        if mode == "disabled":
            raise HTTPException(403, "The Library is locked. Set LIBRARY_TOKEN in the API's .env.")
        if mode == "token":
            expected = self.settings.library_token.get_secret_value()  # type: ignore[union-attr]
            given = (authorization or "").removeprefix("Bearer ").strip()
            if not given or not secrets.compare_digest(given.encode(), expected.encode()):
                raise HTTPException(401, "Enter the Library owner token to continue.")
        return "Owner"

    def require_enabled(self) -> LibraryService:
        if not self.service.enabled:
            raise HTTPException(
                503,
                self.service.problem
                or "Files and the Library are off. Set GEMINI_API_KEY in the API's .env "
                "(or RAG_ENGINE=offline for local testing).",
            )
        return self.service

    def doc_out(self, d: Document) -> DocumentOut:
        coll = self.service.db.get_collection(d.collection_id) if d.collection_id else None
        days = self.settings.chat_file_retention_days
        expires = None
        if d.kind == "chat" and days:
            expires = (d.last_used_at or d.created_at) + days * 86400
        return DocumentOut(
            **{k: v for k, v in d.__dict__.items() if k in DocumentOut.model_fields},
            collection=coll.name if coll else None,
            expires_at=expires,
        )

    @staticmethod
    def fail(exc: RagError) -> HTTPException:
        status = exc.status if isinstance(exc, UploadError) else 502
        return HTTPException(status, str(exc))

    # -------------------------------------------------------------- routers
    def router(self) -> APIRouter:  # noqa: PLR0915 (one closure per endpoint)
        r = APIRouter()
        owner = Depends(self.require_owner)
        svc = self.service

        @r.get("/library/config", response_model=ConfigOut, tags=["library"])
        def config() -> ConfigOut:
            """What the chat needs: on/off, limits, and the collections people can search."""
            return ConfigOut(
                enabled=svc.enabled,
                reason=None
                if svc.enabled
                else svc.problem
                or "Set GEMINI_API_KEY in the API's .env (or RAG_ENGINE=offline for local "
                "testing) to add files and use the Library.",
                engine=svc.engine.name if svc.engine else "",
                label=svc.engine.label if svc.engine else "",
                local=svc.engine.local if svc.engine else False,
                model=svc.engine.model if svc.engine else "",
                owner_auth=self.owner_auth,
                limits=LimitsOut(
                    chat_file_max_bytes=self.settings.chat_file_max_bytes,
                    chat_files_per_message=self.settings.chat_files_per_message,
                    library_file_max_bytes=self.settings.library_file_max_bytes,
                    chat_file_retention_days=self.settings.chat_file_retention_days,
                    extensions=sorted(MIME_TYPES),
                ),
                collections=[_coll(c) for c in svc.collections() if c.documents]
                if svc.enabled
                else [],
            )

        # ---------------------------------------------------------- chat files (anyone)
        @r.post("/files", response_model=DocumentOut, status_code=201, tags=["files"])
        async def upload_chat_file(
            file: Annotated[UploadFile, File()],
            chat_id: Annotated[str, Form(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
        ) -> DocumentOut:
            """Add a file to a chat. It's indexed in the background; poll GET /files/{id}."""
            self.require_enabled()
            started = time.time()
            try:
                doc = await svc.add_file(
                    file.file, file.filename or "file", kind="chat", chat_id=chat_id, actor="Chat"
                )
            except RagError as exc:
                raise self.fail(exc) from exc
            out = self.doc_out(doc)
            out.reused = doc.created_at < started
            return out

        @r.get("/files/{doc_id}", response_model=DocumentOut, tags=["files"])
        def chat_file(doc_id: ID) -> DocumentOut:
            d = svc.db.get_document(doc_id)
            if not d or d.kind != "chat":
                raise HTTPException(404, "This file was deleted")
            return self.doc_out(d)

        @r.delete("/files/{doc_id}", status_code=204, tags=["files"])
        async def delete_chat_file(doc_id: ID) -> None:
            d = svc.db.get_document(doc_id)
            if not d:
                return
            if d.kind != "chat":
                raise HTTPException(403, "Library documents are managed in the Library")
            try:
                await svc.delete_document(doc_id, "Chat")
            except RagError as exc:
                raise self.fail(exc) from exc

        @r.get("/files/{doc_id}/content", tags=["files"])
        def file_content(doc_id: ID) -> FileResponse:
            """The original file. Only PDF and plain text open in the browser; everything
            else downloads (an uploaded HTML file must never run on this site).

            Library originals are included on purpose: answers cite them and anyone who
            can chat can search every collection, so "Open original" works for them too.
            Restricted collections need sign-in first (see the README)."""
            d = svc.db.get_document(doc_id)
            path = svc.file_path(d) if d else None
            if not d or not path or not path.exists():
                raise HTTPException(404, "This file is no longer stored")
            inline = d.mime in {"application/pdf", "text/plain"}
            return FileResponse(
                path,
                media_type=d.mime if inline else "application/octet-stream",
                filename=d.filename,
                content_disposition_type="inline" if inline else "attachment",
                headers={
                    "X-Content-Type-Options": "nosniff",
                    "Content-Security-Policy": "sandbox; default-src 'none'",
                    "Cache-Control": "private, max-age=300",
                },
            )

        # ---------------------------------------------------------- Library (owner)
        @r.get("/library/overview", tags=["library"], dependencies=[owner])
        async def overview() -> dict[str, Any]:
            self.require_enabled()
            data = await svc.overview()
            data["quota_bytes"] = self.settings.storage_quota_bytes
            return data

        @r.get(
            "/library/collections",
            response_model=list[CollectionOut],
            tags=["library"],
            dependencies=[owner],
        )
        def collections() -> list[CollectionOut]:
            return [_coll(c) for c in svc.collections()]

        @r.post(
            "/library/collections", response_model=CollectionOut, status_code=201, tags=["library"]
        )
        def create_collection(body: CollectionIn, actor: str = owner) -> CollectionOut:
            try:
                return _coll(svc.create_collection(body.name, body.description, actor))
            except RagError as exc:
                raise self.fail(exc) from exc

        @r.patch("/library/collections/{cid}", response_model=CollectionOut, tags=["library"])
        def update_collection(cid: ID, body: CollectionIn, actor: str = owner) -> CollectionOut:
            try:
                return _coll(svc.update_collection(cid, body.name, body.description, actor))
            except RagError as exc:
                raise self.fail(exc) from exc

        @r.delete("/library/collections/{cid}", tags=["library"])
        async def delete_collection(cid: ID, actor: str = owner) -> dict[str, int]:
            try:
                return {"deleted_documents": await svc.delete_collection(cid, actor)}
            except RagError as exc:
                raise self.fail(exc) from exc

        @r.get("/library/documents", tags=["library"], dependencies=[owner])
        def documents(
            query: str = Query(default="", max_length=200),
            collection_id: str | None = Query(default=None, pattern=r"^[0-9a-f]{32}$"),
            status: Literal["queued", "processing", "indexed", "failed", "attention"] | None = None,
            limit: int = Query(default=50, ge=1, le=200),
            offset: int = Query(default=0, ge=0),
        ) -> dict[str, Any]:
            docs, total = svc.db.list_documents(
                kind="library",
                collection_id=collection_id,
                status=status,
                query=query.strip(),
                limit=limit,
                offset=offset,
            )
            return {"documents": [self.doc_out(d) for d in docs], "total": total}

        @r.post("/library/documents", tags=["library"], status_code=201)
        async def upload_documents(
            files: Annotated[list[UploadFile], File()],
            collection_id: Annotated[str, Form(pattern=r"^[0-9a-f]{32}$")],
            replace: Annotated[bool, Form()] = False,
            actor: str = owner,
        ) -> dict[str, Any]:
            """Upload several documents to a collection. Each is accepted or rejected on its
            own; accepted ones are indexed in the background."""
            self.require_enabled()
            if len(files) > 50:
                raise HTTPException(422, "Up to 50 files per upload")
            accepted, rejected = [], []
            for f in files:
                try:
                    doc = await svc.add_file(
                        f.file,
                        f.filename or "file",
                        kind="library",
                        collection_id=collection_id,
                        actor=actor,
                        replace=replace,
                    )
                    accepted.append(self.doc_out(doc))
                except UploadError as exc:
                    if exc.status == 404:
                        raise self.fail(exc) from exc
                    rejected.append(
                        {"filename": f.filename, "reason": str(exc), "duplicate": exc.status == 409}
                    )
            return {"accepted": accepted, "rejected": rejected}

        @r.get(
            "/library/documents/{doc_id}",
            response_model=DocumentOut,
            tags=["library"],
            dependencies=[owner],
        )
        def document(doc_id: ID) -> DocumentOut:
            d = svc.db.get_document(doc_id)
            if not d or d.kind != "library":
                raise HTTPException(404, "Document not found")
            return self.doc_out(d)

        @r.post("/library/documents/{doc_id}/reindex", response_model=DocumentOut, tags=["library"])
        async def reindex(doc_id: ID, actor: str = owner) -> DocumentOut:
            self.require_enabled()
            try:
                return self.doc_out(await svc.reindex(doc_id, actor))
            except RagError as exc:
                raise self.fail(exc) from exc

        @r.delete("/library/documents/{doc_id}", status_code=204, tags=["library"])
        async def delete_document(doc_id: ID, actor: str = owner) -> None:
            d = svc.db.get_document(doc_id)
            if not d or d.kind != "library":
                raise HTTPException(404, "Document not found")
            try:
                await svc.delete_document(doc_id, actor)
            except RagError as exc:
                raise self.fail(exc) from exc

        @r.post("/library/documents/bulk", tags=["library"])
        async def bulk(body: BulkIn, actor: str = owner) -> dict[str, Any]:
            done, failed = [], []
            if body.action == "move" and not (
                body.collection_id and svc.db.get_collection(body.collection_id)
            ):
                raise HTTPException(404, "Pick a collection to move to")
            for doc_id in body.ids:
                d = svc.db.get_document(doc_id)
                if not d or d.kind != "library":
                    failed.append({"id": doc_id, "reason": "Document not found"})
                    continue
                try:
                    if body.action == "delete":
                        await svc.delete_document(doc_id, actor)
                    elif body.action == "reindex":
                        await svc.reindex(doc_id, actor)
                    else:
                        if d.status in {"queued", "processing"}:
                            raise UploadError(f"{d.title} is being indexed; move it later", 409)
                        if not svc.file_path(d).exists():
                            raise UploadError(f"The original of {d.title} is missing", 410)
                        svc.db.update_document(doc_id, collection_id=body.collection_id)
                        try:
                            await svc.reindex(doc_id, actor)  # its scope metadata changes
                        except RagError:
                            svc.db.update_document(doc_id, collection_id=d.collection_id)
                            raise
                    done.append(doc_id)
                except RagError as exc:
                    failed.append({"id": doc_id, "reason": str(exc)})
            return {"done": done, "failed": failed}

        @r.post("/library/test", tags=["library"], dependencies=[owner])
        async def test(body: TestIn) -> dict[str, Any]:
            """Ask like a person would and see the answer and the passages it used."""
            self.require_enabled()
            try:
                answer, sources, seconds = await svc.test_question(
                    body.question, body.collection_ids
                )
            except RagError as exc:
                raise self.fail(exc) from exc
            return {
                "answer": answer.text,
                "cited_text": answer.cited_text,
                "grounded": answer.grounded,
                "sources": [s.__dict__ for s in sources],
                "retrieval_queries": answer.retrieval_queries,
                "model": answer.model,
                "seconds": round(seconds, 2),
            }

        @r.get("/library/storage", tags=["library"], dependencies=[owner])
        def storage() -> dict[str, Any]:
            chat, _ = svc.db.list_documents(kind="chat", limit=20, order="size DESC")
            return {
                "totals": svc.db.totals(),
                "quota_bytes": self.settings.storage_quota_bytes,
                "data_dir": str(svc.data_dir.resolve()),
                "largest_chat_files": [self.doc_out(d) for d in chat],
                "chat_file_retention_days": self.settings.chat_file_retention_days,
                "chat_file_max_bytes": self.settings.chat_file_max_bytes,
                "library_file_max_bytes": self.settings.library_file_max_bytes,
            }

        @r.get("/library/settings", tags=["library"], dependencies=[owner])
        async def index_settings(request: Request) -> dict[str, Any]:
            s = self.settings
            store = None
            if svc.engine:
                try:
                    store = await svc.store_id()
                except RagError as exc:
                    store = f"unavailable: {exc}"
            return {
                "engine": svc.engine.name if svc.engine else "",
                "model": svc.engine.model if svc.engine else s.rag_model,
                "embedding_model": s.rag_embedding_model or "service default",
                "store_name": s.rag_store_name,
                "store_id": store,
                "chunk_tokens": s.rag_chunk_tokens,
                "chunk_overlap": s.rag_chunk_overlap,
                "top_k": s.rag_top_k,
                "index_concurrency": s.rag_index_concurrency,
                "owner_auth": self.owner_auth,
                "now": datetime.now(UTC).isoformat(),
            }

        return r
