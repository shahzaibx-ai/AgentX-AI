"""The real google-genai SDK against a local fake of the Gemini REST API.

Checks the requests our Library sends (store, resumable upload with metadata and
chunking, operation polling, streamed generateContent with the fileSearch tool)
and that the streamed grounding becomes [n] citations. Answer quality needs a
real key; this is about wire formats.
"""

import time
from pathlib import Path

import pytest
from google import genai

from app.library import LibrarySettings
from app.library.engine import RagError, Turn
from app.library.gemini import GeminiFileSearchEngine
from tests.conftest import FakeProvider, parse_sse
from tests.fake_gemini_api import FakeGeminiAPI

FIX = Path(__file__).parent / "fixtures" / "library"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    with FakeGeminiAPI() as server:
        yield server


@pytest.fixture
def engine(api):
    client = genai.Client(api_key="test-key", http_options={"base_url": api.url}, vertexai=False)
    return GeminiFileSearchEngine(client, model="gemini-3.8-flash", sleep=lambda _s: None)


def stream_answer(api, store: str, text_parts: list[str]) -> None:
    full = "".join(text_parts)
    chunks = [
        {"candidates": [{"content": {"role": "model", "parts": [{"text": t}]}}]} for t in text_parts
    ]
    chunks[-1]["candidates"][0]["finishReason"] = "STOP"
    chunks[-1]["candidates"][0]["groundingMetadata"] = {
        "groundingChunks": [
            {
                "retrievedContext": {
                    "title": "Employee-Handbook-2026.pdf",
                    "text": "Up to 5 unused days carry over to the next year...",
                    "fileSearchStore": store,
                    "documentName": f"{store}/documents/doc-2",
                    "pageNumber": 2,
                }
            }
        ],
        "groundingSupports": [
            {
                "segment": {"startIndex": 0, "endIndex": len(full.encode())},
                "groundingChunkIndices": [0],
            }
        ],
    }
    api.stream_chunks = chunks


def by_path(api, fragment, method="POST"):
    return [r for r in api.requests if fragment in r["path"] and r["method"] == method]


async def test_store_upload_stream_delete(api, engine):
    store = await engine.ensure_store("assistant-library")
    assert await engine.ensure_store("assistant-library") == store  # found, not duplicated
    assert len(by_path(api, "/v1beta/fileSearchStores")) == 1

    doc = await engine.add_document(
        store,
        FIX / "Employee-Handbook-2026.pdf",
        title="Employee-Handbook-2026.pdf",
        mime_type="application/pdf",
        metadata={"scope": "c:abc", "doc": "d1"},
    )
    init = by_path(api, ":uploadToFileSearchStore")[0]["json"]
    assert init["displayName"] == "Employee-Handbook-2026.pdf"
    assert init["mimeType"] == "application/pdf"
    assert init["customMetadata"] == [
        {"key": "scope", "string_value": "c:abc"},
        {"key": "doc", "string_value": "d1"},
    ]
    assert init["chunkingConfig"] == {
        "white_space_config": {"max_tokens_per_chunk": 400, "max_overlap_tokens": 40}
    }
    assert by_path(api, "/upload/operations/", "GET")
    info = await engine.store_info(store)
    assert info and info.active == 1 and info.size_bytes > 0

    parts = ["Up to 5 unused days carry over ", "and must be taken by 31 March."]
    stream_answer(api, store, parts)
    turns = [Turn("user", "Hi"), Turn("model", "Hello!"), Turn("user", "Carry over?")]
    events = [e async for e in engine.stream(turns, [store], 'scope="c:abc"')]
    assert [e.text for e in events[:-1]] == parts
    answer = events[-1]
    assert answer.cited_text == "".join(parts) + "[1]"
    assert answer.sources[0].page == 2
    assert answer.sources[0].engine_document_id == f"{store}/documents/doc-2"
    sent = by_path(api, ":streamGenerateContent")[-1]
    assert sent["query"] == "alt=sse"
    body = sent["json"]
    assert body["tools"] == [
        {
            "fileSearch": {
                "file_search_store_names": [store],
                "metadata_filter": 'scope="c:abc"',
                "top_k": 6,
            }
        }
    ]
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert "couldn't find that" in body["systemInstruction"]["parts"][0]["text"]

    await engine.delete_document(doc)
    assert by_path(api, doc, "DELETE")
    await engine.delete_document(doc)  # already gone (404) is fine


async def test_blocked_question_is_an_error(api, engine):
    store = await engine.ensure_store("s")
    api.stream_chunks = [{"promptFeedback": {"blockReason": "SAFETY"}}]
    with pytest.raises(RagError, match="blocked the question \\(SAFETY\\)"):
        _ = [e async for e in engine.stream([Turn("user", "x")], [store], None)]


async def test_api_errors_are_readable(api, engine, monkeypatch):
    original = api.handle

    def failing(h, method, body):
        if "fileSearchStores" in h.path:
            return h._send(
                403,
                {
                    "error": {
                        "code": 403,
                        "message": "API key not valid",
                        "status": "PERMISSION_DENIED",
                    }
                },
            )
        return original(h, method, body)

    monkeypatch.setattr(api, "handle", failing)
    with pytest.raises(RagError, match="Gemini API error 403: API key not valid"):
        await engine.ensure_store("s")


def test_whole_app_with_the_real_sdk(api, make_client, tmp_path):
    client_sdk = genai.Client(api_key="k", http_options={"base_url": api.url}, vertexai=False)
    engine = GeminiFileSearchEngine(client_sdk, model="gemini-3.8-flash", sleep=lambda _s: None)
    lib = LibrarySettings(_env_file=None, rag_engine="", library_data_dir=tmp_path / "lib")
    client = make_client(
        FakeProvider("ollama", local=True, models=["m"]), library=lib, library_engine=engine
    )
    cid = client.post("/api/library/collections", json={"name": "HR"}).json()["id"]
    pdf = FIX / "Employee-Handbook-2026.pdf"
    res = client.post(
        "/api/library/documents",
        files=[("files", (pdf.name, pdf.read_bytes()))],
        data={"collection_id": cid},
    ).json()
    doc_id = res["accepted"][0]["id"]
    for _ in range(200):
        doc = client.get(f"/api/library/documents/{doc_id}").json()
        if doc["status"] != "queued" and doc["status"] != "processing":
            break
        time.sleep(0.02)
    assert doc["status"] == "indexed" and doc["engine"] == "gemini"
    store = next(iter(api.stores))
    stream_answer(api, store, ["Up to 5 days carry over."])
    # The chunk's document name doesn't match ours; its `doc` metadata does.
    api.stream_chunks[-1]["candidates"][0]["groundingMetadata"]["groundingChunks"][0][
        "retrievedContext"
    ]["customMetadata"] = [{"key": "doc", "stringValue": doc_id}]
    events = parse_sse(
        client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Carry over?"}],
                "rag": {"collections": [cid]},
            },
        ).text
    )
    assert events[0][1]["provider_label"] == "Gemini File Search"
    sources = dict(events)["sources"]
    assert sources["cited_text"] == "Up to 5 days carry over.[1]"
    assert sources["sources"][0]["document_id"] == doc_id
    assert sources["sources"][0]["collection"] == "HR"
    sent = by_path(api, ":streamGenerateContent")[-1]["json"]
    assert sent["tools"][0]["fileSearch"]["metadata_filter"] == f'scope="c:{cid}"'


async def test_purge_deletes_copies_by_metadata(api, engine):
    store = await engine.ensure_store("s")
    pdf = FIX / "Employee-Handbook-2026.pdf"
    for key in ("d1", "d1", "d2"):
        await engine.add_document(
            store, pdf, title=pdf.name, mime_type="application/pdf", metadata={"doc": key}
        )
    assert await engine.purge(store, "d1") == 2
    assert by_path(api, f"{store}/documents", "GET")  # listed the store
    assert len(by_path(api, "/documents/", "DELETE")) == 2
    assert len(api.docs) == 1
