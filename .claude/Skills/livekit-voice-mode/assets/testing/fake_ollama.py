"""Stand-in Ollama server for tests where real Ollama isn't installed.

Serves GET /api/tags (two chat models + one embedding model, which the app must
hide) and streams a fixed markdown reply from POST /api/chat as NDJSON, so the
real `ollama` Python SDK code path is exercised.

    uv run uvicorn --app-dir <this folder> fake_ollama:app --host 0.0.0.0 --port 11434
"""

import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

DETAILS = {
    "format": "gguf",
    "family": "llama",
    "families": ["llama"],
    "parameter_size": "3.2B",
    "quantization_level": "Q4_K_M",
}

REPLY = "\n".join(
    [
        "Here's a quick **TypeScript** debounce:",
        "",
        "```ts",
        "export function debounce<T extends (...a: any[]) => void>(fn: T, ms = 300) {",
        "  let t: ReturnType<typeof setTimeout>;",
        "  return (...args: Parameters<T>) => {",
        "    clearTimeout(t);",
        "    t = setTimeout(() => fn(...args), ms);",
        "  };",
        "}",
        "```",
        "",
        "| Technique | Runs |",
        "|---|---|",
        "| Debounce | After activity stops |",
        "| Throttle | Once per interval |",
        "",
        "- Rapid calls reset the timer",
        "- `fn` runs once calls stop",
    ]
)


def model(name: str, size: int, **details) -> dict:
    return {
        "name": name,
        "model": name,
        "modified_at": "2026-09-01T00:00:00Z",
        "size": size,
        "digest": name,
        "details": {**DETAILS, **details},
    }


@app.get("/api/tags")
def tags() -> dict:
    return {
        "models": [
            model("llama3.2:latest", 2_019_393_189),
            model(
                "qwen3:8b", 5_200_000_000, family="qwen3", families=["qwen3"], parameter_size="8.2B"
            ),
            model(
                "nomic-embed-text:latest", 274_000_000, family="nomic-bert", families=["nomic-bert"]
            ),
        ]
    }


@app.post("/api/chat")
async def chat(req: Request) -> StreamingResponse:
    body = await req.json()

    def line(content: str, done: bool) -> str:
        data = {
            "model": body["model"],
            "created_at": "2026-09-25T00:00:00Z",
            "message": {"role": "assistant", "content": content},
            "done": done,
        }
        if done:
            data["done_reason"] = "stop"
        return json.dumps(data) + "\n"

    async def gen():
        for token in REPLY.split(" "):
            yield line(token + " ", False)
            await asyncio.sleep(0.01)
        yield line("", True)

    return StreamingResponse(gen(), media_type="application/x-ndjson")
