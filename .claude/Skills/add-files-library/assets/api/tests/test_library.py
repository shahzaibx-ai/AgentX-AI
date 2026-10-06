"""Files in chat and the Library, end to end through the HTTP API with the offline engine."""

import asyncio
import time
from pathlib import Path

import pytest

import app.library as library_pkg
from app.library import LibrarySettings, build_engine
from app.library.engine import NOT_FOUND
from app.library.gemini import GeminiFileSearchEngine
from app.library.offline import OfflineClient
from app.library.service import LibraryService, build_scope_filter
from tests.conftest import FakeProvider, parse_sse

FIX = Path(__file__).parent / "fixtures" / "library"
HANDBOOK = FIX / "Employee-Handbook-2026.pdf"
TRAVEL = FIX / "Travel-Expense-Policy.docx"
FAQ = FIX / "Product-FAQ.md"


@pytest.fixture
def lib(tmp_path) -> LibrarySettings:
    return LibrarySettings(
        _env_file=None,
        rag_engine="offline",
        gemini_api_key=None,
        library_token=None,
        library_data_dir=tmp_path / "lib",
    )


@pytest.fixture
def client(make_client, lib):
    return make_client(FakeProvider("ollama", local=True, models=["llama3.2"]), library=lib)


def wait_indexed(client, doc_id: str, path: str = "/api/files", timeout: float = 10) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        doc = client.get(f"{path}/{doc_id}").json()
        if doc["status"] in {"indexed", "failed"}:
            return doc
        time.sleep(0.02)
    raise AssertionError(f"{doc_id} not indexed: {doc}")


def make_collection(client, name="HR Policies", desc="Handbook and leave") -> str:
    res = client.post("/api/library/collections", json={"name": name, "description": desc})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def upload(client, cid: str, *paths: Path, replace=False) -> dict:
    files = [("files", (p.name, p.read_bytes())) for p in paths]
    res = client.post(
        "/api/library/documents",
        files=files,
        data={"collection_id": cid, "replace": str(replace).lower()},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    for d in body["accepted"]:
        assert wait_indexed(client, d["id"], "/api/library/documents")["status"] == "indexed"
    return body


def chat(client, text: str, *, collections=(), files=(), chat_id=None, **extra) -> list:
    rag = {"collections": list(collections), "files": list(files)}
    if chat_id:
        rag["chat_id"] = chat_id
    body = {"messages": [{"role": "user", "content": text}], "rag": rag, **extra}
    return parse_sse(client.post("/api/chat", json=body).text)


# ---------------------------------------------------------------- config / off
def test_off_without_a_key(make_client):
    client = make_client(FakeProvider("ollama", local=True, models=["llama3.2"]))
    cfg = client.get("/api/library/config").json()
    assert cfg["enabled"] is False and "GEMINI_API_KEY" in cfg["reason"]
    res = client.post("/api/files", files={"file": ("a.txt", b"hi")}, data={"chat_id": "c1"})
    assert res.status_code == 503
    events = chat(client, "hi", collections=["0" * 32])
    assert events[-1][0] == "error"  # library off: no silent fallback to a model


def test_config_lists_searchable_collections(client):
    cfg = client.get("/api/library/config").json()
    assert cfg["enabled"] and cfg["engine"] == "offline" and cfg["owner_auth"] == "open"
    assert cfg["label"] == "Offline search (testing)" and cfg["local"] is True
    assert cfg["model"] == "offline-keyword-search"
    assert cfg["collections"] == []  # empty collections aren't offered
    assert ".pdf" in cfg["limits"]["extensions"] and ".go" in cfg["limits"]["extensions"]
    cid = make_collection(client)
    upload(client, cid, HANDBOOK)
    cfg = client.get("/api/library/config").json()
    assert [(c["name"], c["documents"]) for c in cfg["collections"]] == [("HR Policies", 1)]


# ---------------------------------------------------------------- library management
def test_collections_crud(client):
    cid = make_collection(client)
    dup = client.post("/api/library/collections", json={"name": "hr policies"})
    assert dup.status_code == 409
    res = client.patch(f"/api/library/collections/{cid}", json={"name": "HR", "description": "x"})
    assert res.json()["name"] == "HR"
    upload(client, cid, HANDBOOK, FAQ)
    res = client.delete(f"/api/library/collections/{cid}")
    assert res.json() == {"deleted_documents": 2}
    assert client.get("/api/library/collections").json() == []
    assert client.get("/api/library/documents").json()["total"] == 0


def test_upload_rules_and_duplicates(client, tmp_path):
    cid = make_collection(client)
    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"MZ")
    photo = tmp_path / "pic.jpg"
    photo.write_bytes(b"\xff\xd8\xff")
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    body = upload(client, cid, HANDBOOK, exe, photo, empty)
    reasons = {r["filename"]: r["reason"] for r in body["rejected"]}
    assert ".exe files can't be read" in reasons["setup.exe"]
    assert "is a photo" in reasons["pic.jpg"]
    assert "is empty" in reasons["empty.txt"]
    again = client.post(
        "/api/library/documents",
        files=[("files", (HANDBOOK.name, HANDBOOK.read_bytes()))],
        data={"collection_id": cid},
    ).json()
    assert again["accepted"] == [] and again["rejected"][0]["duplicate"] is True
    replaced = upload(client, cid, HANDBOOK, replace=True)
    assert len(replaced["accepted"]) == 1
    assert client.get("/api/library/documents").json()["total"] == 1
    missing = client.post(
        "/api/library/documents",
        files=[("files", ("a.md", b"# hi"))],
        data={"collection_id": "f" * 32},
    )
    assert missing.status_code == 404


def test_documents_list_filters_and_detail(client):
    hr = make_collection(client)
    fin = make_collection(client, "Finance", "Travel")
    upload(client, hr, HANDBOOK)
    upload(client, fin, TRAVEL)
    all_docs = client.get("/api/library/documents").json()
    assert all_docs["total"] == 2
    only_fin = client.get("/api/library/documents", params={"collection_id": fin}).json()
    assert [d["title"] for d in only_fin["documents"]] == [TRAVEL.name]
    assert only_fin["documents"][0]["collection"] == "Finance"
    q = client.get("/api/library/documents", params={"query": "handbook"}).json()
    assert q["total"] == 1
    tricky = client.get("/api/library/documents", params={"query": "%_"}).json()
    assert tricky["total"] == 0  # LIKE wildcards are escaped
    doc = q["documents"][0]
    detail = client.get(f"/api/library/documents/{doc['id']}").json()
    assert detail["status"] == "indexed" and detail["indexed_at"] and detail["engine"] == "offline"


# ---------------------------------------------------------------- answering in chat
def test_chat_answers_from_a_collection_with_citations(client):
    hr = make_collection(client)
    fin = make_collection(client, "Finance")
    upload(client, hr, HANDBOOK)
    upload(client, fin, TRAVEL)
    events = chat(
        client,
        "How many unused annual leave days can I carry over, and by when?",
        collections=[hr],
        provider="ollama",
        model="llama3.2",
    )
    kinds = [e[0] for e in events]
    assert kinds[0] == "meta" and kinds[-2:] == ["sources", "done"] and "message" in kinds
    meta = events[0][1]
    assert meta["provider_label"].startswith("Offline search")
    assert meta["notice"] and "llama3.2" in meta["notice"]  # says who answered and why
    text = "".join(d["delta"] for k, d in events if k == "message")
    sources = events[-2][1]
    assert "31 March" in text and "[1]" in sources["cited_text"]
    src = sources["sources"][0]
    assert src["title"] == HANDBOOK.name and src["page"] == 2
    assert src["collection"] == "HR Policies" and src["kind"] == "library" and src["cited"]
    doc = client.get("/api/library/documents/" + src["document_id"]).json()
    assert doc["uses"] == 1


def test_scopes_are_isolated(client):
    hr = make_collection(client)
    fin = make_collection(client, "Finance")
    upload(client, hr, HANDBOOK)
    upload(client, fin, TRAVEL)
    events = chat(client, "What is the hotel limit per night in London?", collections=[hr])
    text = "".join(d["delta"] for k, d in events if k == "message")
    assert text.strip() == NOT_FOUND
    assert events[-2] == ("sources", {"cited_text": NOT_FOUND, "grounded": False, "sources": []})
    both = chat(client, "What is the hotel limit per night in London?", collections=[hr, fin])
    assert "$180" in "".join(d["delta"] for k, d in both if k == "message")


def test_chat_files_flow(client):
    up = client.post(
        "/api/files", files={"file": (FAQ.name, FAQ.read_bytes())}, data={"chat_id": "chat-1"}
    )
    assert up.status_code == 201
    doc = wait_indexed(client, up.json()["id"])
    assert doc["kind"] == "chat" and doc["expires_at"] > time.time() + 29 * 86400
    same = client.post(
        "/api/files", files={"file": ("copy.md", FAQ.read_bytes())}, data={"chat_id": "chat-1"}
    )
    assert same.json()["id"] == doc["id"]  # same file in the same chat is reused
    assert same.json()["reused"] is True and up.json()["reused"] is False
    events = chat(client, "How many requests per minute can each API key make?", files=[doc["id"]])
    assert "600" in "".join(d["delta"] for k, d in events if k == "message")
    assert events[-2][1]["sources"][0]["kind"] == "chat"
    # Another chat's file isn't searchable without its id
    other = client.post(
        "/api/files", files={"file": (TRAVEL.name, TRAVEL.read_bytes())}, data={"chat_id": "c2"}
    ).json()
    wait_indexed(client, other["id"])
    miss = chat(client, "What is the hotel limit per night in London?", files=[doc["id"]])
    assert "".join(d["delta"] for k, d in miss if k == "message").strip() == NOT_FOUND
    assert client.delete(f"/api/files/{doc['id']}").status_code == 204
    assert client.get(f"/api/files/{doc['id']}").status_code == 404
    gone = chat(client, "Rate limit?", files=[doc["id"]])
    assert gone[-1][0] == "error" and "no longer available" in gone[-1][1]["message"]
    assert "kept 30 days" in gone[-1][1]["message"]

    # An expired earlier file doesn't break the chat: it's skipped with a note.
    fresh = client.post(
        "/api/files", files={"file": (FAQ.name, FAQ.read_bytes())}, data={"chat_id": "chat-1"}
    ).json()
    wait_indexed(client, fresh["id"])
    ok = chat(client, "Rate limit per minute?", files=[doc["id"], fresh["id"]], chat_id="chat-1")
    meta = dict(ok)["meta"]
    assert "1 earlier file in this chat is no longer available" in meta["notice"]
    assert "600" in "".join(d["delta"] for k, d in ok if k == "message")

    # Only this chat's files: another chat's file id is ignored.
    other_only = chat(client, "Hotel limit in London?", files=[other["id"]], chat_id="chat-1")
    assert other_only[-1][0] == "error" and "no longer available" in other_only[-1][1]["message"]
    mixed = chat(
        client, "Hotel limit in London?", files=[fresh["id"], other["id"]], chat_id="chat-1"
    )
    assert "".join(d["delta"] for k, d in mixed if k == "message").strip() == NOT_FOUND


def test_library_document_ids_are_not_chat_files(client):
    cid = client.post("/api/library/collections", json={"name": "HR"}).json()["id"]
    up = client.post(
        "/api/library/documents",
        files=[("files", (FAQ.name, FAQ.read_bytes()))],
        data={"collection_id": cid},
    ).json()["accepted"][0]
    lib_doc = wait_indexed(client, up["id"], "/api/library/documents")
    assert lib_doc["status"] == "indexed"
    # A Library document id passed as a "file" doesn't bypass picking its collection.
    events = chat(client, "Rate limit per minute?", files=[lib_doc["id"]])
    assert events[-1][0] == "error"
    # Chat-file metadata isn't served for Library documents; the original is (cited answers).
    assert client.get(f"/api/files/{lib_doc['id']}").status_code == 404
    assert client.get(f"/api/files/{lib_doc['id']}/content").status_code == 200


async def test_purge_removes_orphan_copies():
    engine = GeminiFileSearchEngine(OfflineClient(), model="m", name="offline")
    store = await engine.ensure_store("s")
    for _ in range(2):  # e.g. a timed-out upload that finished later, then a retry
        await engine.add_document(
            store,
            FAQ,
            title=FAQ.name,
            mime_type="text/markdown",
            metadata={"scope": "c:x", "doc": "d1"},
        )
    await engine.add_document(
        store,
        FAQ,
        title=FAQ.name,
        mime_type="text/markdown",
        metadata={"scope": "c:x", "doc": "d2"},
    )
    assert await engine.purge(store, "d1") == 2
    info = await engine.store_info(store)
    assert info and info.active == 1


def test_chat_file_rules(make_client, tmp_path):
    lib = LibrarySettings(
        _env_file=None,
        rag_engine="offline",
        library_data_dir=tmp_path / "l",
        chat_file_max_bytes=1024 * 1024,
    )
    client = make_client(FakeProvider("ollama", local=True, models=["m"]), library=lib)
    big = client.post(
        "/api/files", files={"file": ("big.txt", b"x" * (1024 * 1024 + 1))}, data={"chat_id": "c"}
    )
    assert big.status_code == 413 and "over the 1.0 MB limit" in big.json()["detail"]
    pic = client.post("/api/files", files={"file": ("a.png", b"\x89PNG")}, data={"chat_id": "c"})
    assert pic.status_code == 415
    bad_chat = client.post("/api/files", files={"file": ("a.md", b"# x")}, data={"chat_id": "../x"})
    assert bad_chat.status_code == 422
    assert client.get(f"/api/files/{'a' * 32}").status_code == 404


def test_file_still_indexing_and_failed(client):
    svc = client.app.state.library
    queued = svc.db.insert_document(
        kind="chat",
        chat_id="c",
        title="slow.pdf",
        filename="slow.pdf",
        ext=".pdf",
        mime="application/pdf",
        size=10,
        sha256="x",
        status="processing",
    )
    events = chat(client, "Summarise", files=[queued.id])
    assert events[-1] == (
        "error",
        {"message": "slow.pdf is still being indexed. Try again in a moment."},
    )
    svc.db.update_document(queued.id, status="failed", error="No text found")
    events = chat(client, "Summarise", files=[queued.id])
    assert "couldn't be indexed: No text found" in events[-1][1]["message"]


def test_unreadable_file_fails_with_a_reason(client):
    res = client.post(
        "/api/files", files={"file": ("blank.txt", b"   \n  ")}, data={"chat_id": "c"}
    )
    doc = wait_indexed(client, res.json()["id"])
    assert doc["status"] == "failed" and "No text could be extracted" in doc["error"]


def test_history_is_sent_as_alternating_turns(client):
    hr = make_collection(client)
    upload(client, hr, HANDBOOK)
    body = {
        "messages": [
            {"role": "assistant", "content": "Hi! How can I help?"},
            {"role": "user", "content": "Tell me about leave."},
            {"role": "assistant", "content": "Sure."},
            {"role": "user", "content": "How much is the home office allowance?"},
        ],
        "rag": {"collections": [hr]},
    }
    events = parse_sse(client.post("/api/chat", json=body).text)
    assert "$500" in "".join(d["delta"] for k, d in events if k == "message")


# ---------------------------------------------------------------- owner actions
def test_reindex_bulk_move_and_delete(client):
    hr = make_collection(client)
    fin = make_collection(client, "Finance")
    body = upload(client, hr, HANDBOOK, TRAVEL)
    ids = {d["title"]: d["id"] for d in body["accepted"]}
    res = client.post(f"/api/library/documents/{ids[HANDBOOK.name]}/reindex")
    assert res.status_code == 200
    wait_indexed(client, ids[HANDBOOK.name], "/api/library/documents")
    moved = client.post(
        "/api/library/documents/bulk",
        json={"action": "move", "ids": [ids[TRAVEL.name]], "collection_id": fin},
    ).json()
    assert moved == {"done": [ids[TRAVEL.name]], "failed": []}
    wait_indexed(client, ids[TRAVEL.name], "/api/library/documents")
    q = "What is the hotel limit per night in London?"
    assert "$180" in "".join(
        d["delta"] for k, d in chat(client, q, collections=[fin]) if k == "message"
    )
    hr_only = "".join(d["delta"] for k, d in chat(client, q, collections=[hr]) if k == "message")
    assert hr_only.strip() == NOT_FOUND  # the move changed its scope in the index
    deleted = client.post(
        "/api/library/documents/bulk", json={"action": "delete", "ids": list(ids.values())}
    ).json()
    assert len(deleted["done"]) == 2
    store = client.app.state.library.engine.client._stores
    assert all(not s["docs"] for s in store.values())  # removed from the index too


def test_retrieval_test_overview_storage_settings(client):
    hr = make_collection(client)
    upload(client, hr, HANDBOOK)
    res = client.post(
        "/api/library/test", json={"question": "How much is the home office allowance?"}
    )
    body = res.json()
    assert "$500" in body["answer"] and body["sources"][0]["title"] == HANDBOOK.name
    chat(client, "How much is the home office allowance?", collections=[hr])
    ov = client.get("/api/library/overview").json()
    assert ov["totals"]["library_documents"] == 1 and ov["queue"] == 0
    assert sum(ov["searches"].values()) == 1 and len(ov["searches"]) == 14
    assert ov["store"]["active"] == 1
    assert any("uploaded" in a["text"] for a in ov["activity"])
    st = client.get("/api/library/storage").json()
    assert st["totals"]["library_size"] == HANDBOOK.stat().st_size
    cfg = client.get("/api/library/settings").json()
    assert cfg["engine"] == "offline" and cfg["chunk_tokens"] == 400


def test_original_files_are_served_safely(client):
    pdf = client.post(
        "/api/files", files={"file": (HANDBOOK.name, HANDBOOK.read_bytes())}, data={"chat_id": "c"}
    ).json()
    html = client.post(
        "/api/files",
        files={"file": ("page.html", b"<script>alert(1)</script>")},
        data={"chat_id": "c"},
    ).json()
    r = client.get(f"/api/files/{pdf['id']}/content")
    assert (
        r.headers["content-type"] == "application/pdf"
        and "inline" in r.headers["content-disposition"]
    )
    r = client.get(f"/api/files/{html['id']}/content")
    assert r.headers["content-type"] == "application/octet-stream"
    assert "attachment" in r.headers["content-disposition"]
    assert "sandbox" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_owner_token(make_client, tmp_path):
    lib = LibrarySettings(
        _env_file=None,
        rag_engine="offline",
        library_data_dir=tmp_path / "l",
        library_token="s3cret-token",
    )
    client = make_client(FakeProvider("ollama", local=True, models=["m"]), library=lib)
    assert client.get("/api/library/config").json()["owner_auth"] == "token"
    assert client.get("/api/library/collections").status_code == 401
    bad = client.get("/api/library/collections", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    ok = client.get("/api/library/collections", headers={"Authorization": "Bearer s3cret-token"})
    assert ok.status_code == 200
    # Chat files don't need the owner token.
    up = client.post(
        "/api/files", files={"file": ("a.md", b"# Hello world")}, data={"chat_id": "c"}
    )
    assert up.status_code == 201


def test_production_without_token_locks_the_library(make_client, tmp_path):
    lib = LibrarySettings(_env_file=None, rag_engine="offline", library_data_dir=tmp_path / "l")
    client = make_client(
        FakeProvider("ollama", local=True, models=["m"]), library=lib, environment="production"
    )
    assert client.get("/api/library/config").json()["owner_auth"] == "disabled"
    res = client.get("/api/library/overview")
    assert res.status_code == 403 and "LIBRARY_TOKEN" in res.json()["detail"]


# ---------------------------------------------------------------- service lifecycle
async def test_resume_retention_and_engine_switch(tmp_path):
    lib = LibrarySettings(_env_file=None, rag_engine="offline", library_data_dir=tmp_path / "l")
    svc = LibraryService(lib, build_engine(lib))
    queued = svc.db.insert_document(
        kind="chat",
        chat_id="c",
        title="a.md",
        filename="a.md",
        ext=".md",
        mime="text/markdown",
        size=12,
        sha256="1",
        status="processing",
    )
    svc.file_path(queued).write_text("# Rate limits\nEach key may make 600 requests a minute.")
    other = svc.db.insert_document(
        kind="chat",
        chat_id="c",
        title="b.md",
        filename="b.md",
        ext=".md",
        mime="text/markdown",
        size=12,
        sha256="2",
        status="indexed",
        engine="old-engine",
        engine_doc_id="x",
    )
    svc.file_path(other).write_text("# Retention\nLogs are kept for 90 days.")
    await svc.start()
    await asyncio.wait_for(svc.drain(), 5)
    assert svc.db.get_document(queued.id).status == "indexed"  # resumed after "restart"
    b = svc.db.get_document(other.id)
    assert b.status == "indexed" and b.engine == "offline"  # re-indexed for the new engine
    svc.db.update_document(other.id, created_at=0)
    assert await svc.sweep_chat_files() == 1
    assert svc.db.get_document(other.id) is None and not svc.file_path(other).exists()
    await svc.stop()


def test_scope_filter():
    assert build_scope_filter(["a"], []) == 'scope="c:a"'
    assert build_scope_filter(["a"], ["d1", 'x"y']) == '(scope="c:a" OR doc="d1" OR doc="x\\"y")'
    with pytest.raises(Exception, match="Nothing to search"):
        build_scope_filter([], [])


def test_a_broken_library_never_stops_the_api(make_client, tmp_path, monkeypatch):
    """A missing package or bad setting turns the Library off; chat, models and the
    rest of the API (voice mode included) keep working."""

    def missing(_settings):
        raise ModuleNotFoundError("No module named 'google.genai'", name="google.genai")

    monkeypatch.setattr(library_pkg, "build_engine", missing)
    lib = LibrarySettings(_env_file=None, rag_engine="gemini", library_data_dir=tmp_path / "l")
    client = make_client(FakeProvider("ollama", local=True, models=["llama3.2"]), library=lib)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/models").status_code == 200
    cfg = client.get("/api/library/config").json()
    assert (
        cfg["enabled"] is False
        and "google-genai package" in cfg["reason"]
        and "uv sync" in cfg["reason"]
    )
    up = client.post("/api/files", files={"file": ("a.txt", b"hi")}, data={"chat_id": "c1"})
    assert up.status_code == 503 and "uv sync" in up.json()["detail"]
    events = parse_sse(
        client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).text
    )
    assert events[-1][0] == "done"


def test_an_unwritable_data_dir_never_stops_the_api(make_client, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    lib = LibrarySettings(_env_file=None, rag_engine="offline", library_data_dir=blocker / "lib")
    client = make_client(FakeProvider("ollama", local=True, models=["llama3.2"]), library=lib)
    assert client.get("/api/models").status_code == 200
    cfg = client.get("/api/library/config").json()
    assert cfg["enabled"] is False and "could not start" in cfg["reason"]
