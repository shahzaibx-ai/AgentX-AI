"""The Library's own records in SQLite: collections, documents, activity, search counts.

The search index lives in the RAG engine (Gemini File Search today); this
database is the source of truth for what exists, who added it, its status and
where the original file is. Queries are tiny and local, so they run inline.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('library', 'chat')),
    collection_id TEXT REFERENCES collections(id),
    chat_id TEXT,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    ext TEXT NOT NULL,
    mime TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'indexed', 'failed')),
    step TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    engine TEXT NOT NULL DEFAULT '',
    engine_doc_id TEXT NOT NULL DEFAULT '',
    uploaded_by TEXT NOT NULL DEFAULT '',
    uses INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    indexed_at REAL,
    last_used_at REAL
);
CREATE INDEX IF NOT EXISTS documents_collection ON documents(collection_id);
CREATE INDEX IF NOT EXISTS documents_chat ON documents(chat_id);
CREATE INDEX IF NOT EXISTS documents_engine_doc ON documents(engine_doc_id);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
    day TEXT PRIMARY KEY,
    count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Collection:
    id: str
    name: str
    description: str
    created_at: float
    updated_at: float
    documents: int = 0
    size: int = 0


@dataclass
class Document:
    id: str
    kind: str
    collection_id: str | None
    chat_id: str | None
    title: str
    filename: str
    ext: str
    mime: str
    size: int
    sha256: str
    status: str
    step: str
    error: str
    engine: str
    engine_doc_id: str
    uploaded_by: str
    uses: int
    created_at: float
    updated_at: float
    indexed_at: float | None
    last_used_at: float | None


_DOC_FIELDS = [f.name for f in fields(Document)]


def new_id() -> str:
    return uuid.uuid4().hex


class LibraryDB:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _all(self, sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, tuple(args)).fetchall()

    def _one(self, sql: str, args: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, tuple(args)).fetchone()

    def _run(self, sql: str, args: Iterable[Any] = ()) -> int:
        with self._lock:
            return self._conn.execute(sql, tuple(args)).rowcount

    # ------------------------------------------------------------------ key/value
    def get_kv(self, key: str) -> str | None:
        row = self._one("SELECT value FROM kv WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_kv(self, key: str, value: str) -> None:
        self._run("INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)", (key, value))

    # ------------------------------------------------------------------ collections
    def list_collections(self) -> list[Collection]:
        rows = self._all(
            """SELECT c.*, COUNT(d.id) AS documents, COALESCE(SUM(d.size), 0) AS size
               FROM collections c LEFT JOIN documents d ON d.collection_id = c.id
               GROUP BY c.id ORDER BY c.name COLLATE NOCASE"""
        )
        return [Collection(**dict(r)) for r in rows]

    def get_collection(self, collection_id: str) -> Collection | None:
        return next((c for c in self.list_collections() if c.id == collection_id), None)

    def collection_by_name(self, name: str) -> Collection | None:
        row = self._one("SELECT id FROM collections WHERE name = ? COLLATE NOCASE", (name,))
        return self.get_collection(row["id"]) if row else None

    def create_collection(self, name: str, description: str) -> Collection:
        now = time.time()
        cid = new_id()
        self._run(
            "INSERT INTO collections (id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, name, description, now, now),
        )
        result = self.get_collection(cid)
        assert result is not None
        return result

    def update_collection(self, collection_id: str, name: str, description: str) -> None:
        self._run(
            "UPDATE collections SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, time.time(), collection_id),
        )

    def delete_collection(self, collection_id: str) -> None:
        self._run("DELETE FROM collections WHERE id = ?", (collection_id,))

    # ------------------------------------------------------------------ documents
    def insert_document(self, **values: Any) -> Document:
        now = time.time()
        row = {
            "id": new_id(),
            "collection_id": None,
            "chat_id": None,
            "status": "queued",
            "step": "Waiting to be indexed",
            "error": "",
            "engine": "",
            "engine_doc_id": "",
            "uploaded_by": "",
            "uses": 0,
            "created_at": now,
            "updated_at": now,
            "indexed_at": None,
            "last_used_at": None,
            **values,
        }
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        self._run(f"INSERT INTO documents ({cols}) VALUES ({marks})", row.values())
        doc = self.get_document(row["id"])
        assert doc is not None
        return doc

    def get_document(self, document_id: str) -> Document | None:
        row = self._one("SELECT * FROM documents WHERE id = ?", (document_id,))
        return Document(**dict(row)) if row else None

    def update_document(self, document_id: str, **values: Any) -> None:
        unknown = set(values) - set(_DOC_FIELDS)
        if unknown:
            raise ValueError(f"Unknown document fields: {unknown}")
        values["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in values)
        self._run(f"UPDATE documents SET {sets} WHERE id = ?", [*values.values(), document_id])

    def delete_document(self, document_id: str) -> None:
        self._run("DELETE FROM documents WHERE id = ?", (document_id,))

    def list_documents(
        self,
        *,
        kind: str | None = None,
        collection_id: str | None = None,
        chat_id: str | None = None,
        status: str | None = None,
        query: str = "",
        limit: int = 1000,
        offset: int = 0,
        order: str = "created_at DESC",
    ) -> tuple[list[Document], int]:
        where, args = ["1 = 1"], []
        if kind:
            where.append("kind = ?")
            args.append(kind)
        if collection_id:
            where.append("collection_id = ?")
            args.append(collection_id)
        if chat_id:
            where.append("chat_id = ?")
            args.append(chat_id)
        if status == "attention":
            where.append("status = 'failed'")
        elif status:
            where.append("status = ?")
            args.append(status)
        if query:
            where.append("(title LIKE ? ESCAPE '\\' OR filename LIKE ? ESCAPE '\\')")
            like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            args += [like, like]
        if order not in {"created_at DESC", "size DESC", "uses DESC"}:
            raise ValueError("Unsupported order")
        clause = " AND ".join(where)
        total = self._one(f"SELECT COUNT(*) AS n FROM documents WHERE {clause}", args)
        rows = self._all(
            f"SELECT * FROM documents WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
            [*args, limit, offset],
        )
        return [Document(**dict(r)) for r in rows], int(total["n"] if total else 0)

    def find_duplicate(self, kind: str, sha256: str, scope_id: str | None) -> Document | None:
        col = "collection_id" if kind == "library" else "chat_id"
        row = self._one(
            f"SELECT * FROM documents WHERE kind = ? AND sha256 = ? AND {col} IS ?",
            (kind, sha256, scope_id),
        )
        return Document(**dict(row)) if row else None

    def documents_by_engine_ids(self, ids: Iterable[str]) -> dict[str, Document]:
        ids = [i for i in ids if i]
        if not ids:
            return {}
        marks = ", ".join("?" for _ in ids)
        rows = self._all(f"SELECT * FROM documents WHERE engine_doc_id IN ({marks})", ids)
        return {r["engine_doc_id"]: Document(**dict(r)) for r in rows}

    def mark_used(self, document_ids: Iterable[str]) -> None:
        now = time.time()
        for did in set(document_ids):
            self._run(
                "UPDATE documents SET uses = uses + 1, last_used_at = ? WHERE id = ?", (now, did)
            )

    def unfinished_documents(self) -> list[Document]:
        rows = self._all(
            "SELECT * FROM documents WHERE status IN ('queued', 'processing') ORDER BY created_at"
        )
        return [Document(**dict(r)) for r in rows]

    def expired_chat_documents(self, before: float) -> list[Document]:
        rows = self._all(
            "SELECT * FROM documents WHERE kind = 'chat' "
            "AND COALESCE(last_used_at, created_at) < ?",
            (before,),
        )
        return [Document(**dict(r)) for r in rows]

    def totals(self) -> dict[str, Any]:
        rows = self._all(
            "SELECT kind, status, COUNT(*) AS n, COALESCE(SUM(size), 0) AS size "
            "FROM documents GROUP BY kind, status"
        )
        out: dict[str, Any] = {"by_status": {}, "library_size": 0, "chat_size": 0, "chat_files": 0}
        for r in rows:
            if r["kind"] == "library":
                out["by_status"][r["status"]] = out["by_status"].get(r["status"], 0) + r["n"]
                out["library_size"] += r["size"]
            else:
                out["chat_size"] += r["size"]
                out["chat_files"] += r["n"]
        out["library_documents"] = sum(out["by_status"].values())
        return out

    # ------------------------------------------------------------------ activity + searches
    def log(self, actor: str, text: str) -> None:
        self._run(
            "INSERT INTO activity (at, actor, text) VALUES (?, ?, ?)", (time.time(), actor, text)
        )
        self._run("DELETE FROM activity WHERE id <= (SELECT MAX(id) - 500 FROM activity)")

    def recent_activity(self, limit: int = 8) -> list[dict[str, Any]]:
        rows = self._all("SELECT at, actor, text FROM activity ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def count_search(self, day: str) -> None:
        self._run(
            "INSERT INTO searches (day, count) VALUES (?, 1) "
            "ON CONFLICT(day) DO UPDATE SET count = count + 1",
            (day,),
        )

    def searches(self, days: list[str]) -> dict[str, int]:
        marks = ", ".join("?" for _ in days)
        rows = self._all(f"SELECT day, count FROM searches WHERE day IN ({marks})", days)
        found = {r["day"]: r["count"] for r in rows}
        return {d: found.get(d, 0) for d in days}
