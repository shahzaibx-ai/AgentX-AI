"""Stand-in Ollama with one text model and one vision model, for photo tests.

    uv run --with fastapi --with uvicorn uvicorn fake_ollama_vision:app --port 11434

- /api/tags lists llama3.2:latest (text) and gemma3:4b (vision)
- /api/show returns each model's capabilities (["completion", "vision"] for gemma3)
- /api/chat streams a short NDJSON reply that says how many photos arrived
- GET /log returns what each chat request received: model, roles, text, and per
  image the decoded byte count and first four bytes in hex (ffd8ff.. = JPEG,
  89504e47 = PNG). Photo tests assert on it.
"""

import asyncio
import base64
import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
LOG: list[dict] = []
DETAILS = {"format": "gguf", "family": "llama", "families": ["llama"], "parameter_size": "3.2B",
           "quantization_level": "Q4_K_M"}  # fmt: skip
MODELS = {
    "llama3.2:latest": (DETAILS, ["completion", "tools"]),
    "gemma3:4b": (
        {**DETAILS, "family": "gemma3", "families": ["gemma3"], "parameter_size": "4.3B"},
        ["completion", "vision"],
    ),
}


@app.get("/api/tags")
def tags():
    return {
        "models": [
            {"name": n, "model": n, "modified_at": "2026-09-01T00:00:00Z", "size": 3_000_000_000,
             "digest": f"sha256-{n}", "details": d}  # fmt: skip
            for n, (d, _) in MODELS.items()
        ]
    }


@app.post("/api/show")
async def show(req: Request):
    body = await req.json()
    details, caps = MODELS[body.get("model") or body.get("name")]
    return {"modelfile": "", "parameters": "", "template": "", "details": details,
            "model_info": {}, "capabilities": caps}  # fmt: skip


@app.get("/log")
def log():
    return LOG


@app.delete("/log")
def clear_log():
    LOG.clear()
    return {"ok": True}


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    entry = {"model": body["model"], "messages": []}
    for m in body["messages"]:
        images = []
        for b64 in m.get("images") or []:
            raw = base64.b64decode(b64)
            images.append({"bytes": len(raw), "head": raw[:4].hex()})
        # The Ollama SDK leaves out empty fields, so a photo-only message has no "content".
        entry["messages"].append({"role": m["role"], "content": m.get("content", ""), "images": images})
    LOG.append(entry)

    n = len(body["messages"][-1].get("images") or [])
    reply = f"I can see {n} photo(s). The receipt total is **$35.64**." if n else "Text reply."

    async def gen():
        await asyncio.sleep(0.6)  # long enough to see the "Looking at…" state
        for tok in reply.split(" "):
            yield json.dumps({"model": body["model"], "created_at": "2026-09-25T00:00:00Z",
                              "message": {"role": "assistant", "content": tok + " "}, "done": False}) + "\n"  # fmt: skip  # noqa: E501
            await asyncio.sleep(0.02)
        yield json.dumps({"model": body["model"], "created_at": "2026-09-25T00:00:00Z",
                          "message": {"role": "assistant", "content": ""}, "done": True,
                          "done_reason": "stop"}) + "\n"  # fmt: skip

    return StreamingResponse(gen(), media_type="application/x-ndjson")
