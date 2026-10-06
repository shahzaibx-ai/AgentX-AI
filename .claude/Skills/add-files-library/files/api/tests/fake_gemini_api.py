"""A tiny HTTP server that speaks the parts of the Gemini REST API File Search uses.

The contract test points the *real* google-genai SDK at it, so we check the
actual requests the SDK sends for our engine (resumable upload, operation
polling, generateContent with the fileSearch tool) and that our code reads the
real response shapes. Answers are canned; this is about wire formats.
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class FakeGeminiAPI:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.stores: dict[str, dict[str, Any]] = {}
        self.uploads: dict[str, dict[str, Any]] = {}  # session -> {store, meta, bytes}
        self.ops: dict[str, dict[str, Any]] = {}
        self.docs: dict[str, dict[str, Any]] = {}
        self.polls: dict[str, int] = {}
        self.answer: dict[str, Any] = {}
        self.stream_chunks: list[dict[str, Any]] = []
        self._n = 0
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_a: Any) -> None:
                pass

            def _body(self) -> bytes:
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def _send(self, code: int, body: Any = None, headers: dict[str, str] | None = None):
                data = json.dumps(body if body is not None else {}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                api.handle(self, "GET", b"")

            def do_POST(self) -> None:
                api.handle(self, "POST", self._body())

            def do_DELETE(self) -> None:
                api.handle(self, "DELETE", b"")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> FakeGeminiAPI:
        self.thread.start()
        return self

    def __exit__(self, *_a: Any) -> None:
        self.server.shutdown()
        self.server.server_close()

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n}"

    def handle(self, h: Any, method: str, body: bytes) -> None:  # noqa: PLR0911, PLR0912 (one branch per route)
        path, _, query = h.path.partition("?")
        is_json = body[:1] in (b"{", b"[")
        self.requests.append(
            {
                "method": method,
                "path": path,
                "query": query,
                "json": json.loads(body) if is_json else None,
                "headers": {k.lower(): v for k, v in h.headers.items()},
                "size": len(body),
            }
        )
        m = re.fullmatch(r"/v1beta/fileSearchStores", path)
        if m and method == "POST":
            name = "fileSearchStores/" + self._id("store-")
            self.stores[name] = {"name": name, "displayName": json.loads(body).get("displayName")}
            return h._send(200, self.stores[name])
        if m and method == "GET":
            return h._send(200, {"fileSearchStores": list(self.stores.values())})
        m = re.fullmatch(r"/v1beta/(fileSearchStores/[^/:]+)", path)
        if m and method == "DELETE":
            self.stores.pop(m.group(1), None)
            return h._send(200, {})
        if m and method == "GET":
            store = self.stores.get(m.group(1))
            if not store:
                return h._send(404, {"error": {"code": 404, "message": "not found"}})
            docs = [d for n, d in self.docs.items() if n.startswith(m.group(1) + "/")]
            return h._send(
                200,
                {
                    **store,
                    "activeDocumentsCount": str(len(docs)),
                    "sizeBytes": str(sum(int(d["sizeBytes"]) for d in docs)),
                },
            )
        m = re.fullmatch(r"/upload/v1beta/(fileSearchStores/[^/:]+):uploadToFileSearchStore", path)
        if m and method == "POST":
            session = self._id("session-")
            self.uploads[session] = {"store": m.group(1), "meta": json.loads(body), "bytes": 0}
            return h._send(200, {}, {"x-goog-upload-url": f"{self.url}/upload-session/{session}"})
        m = re.fullmatch(r"/upload-session/(.+)", path)
        if m and method == "POST":
            up = self.uploads[m.group(1)]
            up["bytes"] += len(body)
            op = f"{up['store']}/upload/operations/{self._id('op-')}"
            doc = f"{up['store']}/documents/{self._id('doc-')}"
            meta = up["meta"]
            self.ops[op] = {
                "name": op,
                "done": True,
                "response": {"parent": up["store"], "documentName": doc},
            }
            self.docs[doc] = {
                "name": doc,
                "displayName": meta.get("displayName"),
                "state": "STATE_ACTIVE",
                "sizeBytes": str(up["bytes"]),
                "mimeType": meta.get("mimeType"),
                "customMetadata": meta.get("customMetadata", []),
            }
            return h._send(200, {"name": op, "done": False}, {"x-goog-upload-status": "final"})
        m = re.fullmatch(r"/v1beta/(fileSearchStores/.+/operations/.+)", path)
        if m and method == "GET":
            return h._send(200, self.ops[m.group(1)])
        m = re.fullmatch(r"/v1beta/(fileSearchStores/[^/]+)/documents", path)
        if m and method == "GET":
            docs = [d for n, d in self.docs.items() if n.startswith(m.group(1) + "/")]
            return h._send(200, {"documents": docs})
        m = re.fullmatch(r"/v1beta/(fileSearchStores/[^/]+/documents/[^/]+)", path)
        if m and method == "GET":
            return h._send(200, self.docs[m.group(1)])
        if m and method == "DELETE":
            self.docs.pop(m.group(1), None)
            return h._send(200, {})
        m = re.fullmatch(r"/v1beta/models/([^:]+):streamGenerateContent", path)
        if m and method == "POST":
            # Server-sent events, one JSON response per chunk (alt=sse).
            data = "".join(f"data: {json.dumps(c)}\r\n\r\n" for c in self.stream_chunks).encode()
            h.send_response(200)
            h.send_header("Content-Type", "text/event-stream")
            h.send_header("Content-Length", str(len(data)))
            h.end_headers()
            h.wfile.write(data)
            return None
        m = re.fullmatch(r"/v1beta/models/([^:]+):generateContent", path)
        if m and method == "POST":
            return h._send(200, self.answer)
        return h._send(404, {"error": {"code": 404, "message": f"no route {method} {path}"}})
