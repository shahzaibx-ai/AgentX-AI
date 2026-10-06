"""Turn a Gemini response with File Search grounding into an `Answer`.

Grounding metadata has two lists:
- `grounding_chunks`: the passages File Search retrieved (title, text, page).
- `grounding_supports`: which answer segment each passage backs. Segment
  offsets are in **bytes** of the UTF-8 text of one response part.

We number the passages in the order the answer first cites them, put `[n]`
after each supported segment, and keep only passages the answer used (or all
retrieved passages if the model returned none of the support links).
"""

from __future__ import annotations

from typing import Any

from google.genai import types

from .engine import Answer, RagError, Source, is_not_found


def _parts_text(candidate: types.Candidate) -> list[str]:
    content = candidate.content
    if not content or not content.parts:
        return []
    # Keep one entry per part so segment `part_index` values line up; thoughts are hidden.
    return ["" if getattr(p, "thought", False) else (p.text or "") for p in content.parts]


def _page(ctx: types.GroundingChunkRetrievedContext) -> int | None:
    if ctx.page_number:
        return int(ctx.page_number)
    span = getattr(ctx.rag_chunk, "page_span", None) if ctx.rag_chunk else None
    first = getattr(span, "first_page", None) if span else None
    return int(first) if first else None


def _insert_markers(parts: list[str], marks: dict[tuple[int, int], list[int]]) -> str:
    """Insert ` [1][2]` at byte offsets per part, then join the parts."""
    out: list[str] = []
    for part_index, text in enumerate(parts):
        data = text.encode("utf-8")
        cuts = sorted((end, nums) for (p, end), nums in marks.items() if p == part_index)
        pieces: list[bytes] = []
        last = 0
        for end, nums in cuts:
            end = max(last, min(end, len(data)))
            # Never split a multi-byte character: move to the next character boundary.
            while end < len(data) and (data[end] & 0xC0) == 0x80:
                end += 1
            pieces.append(data[last:end])
            pieces.append(("".join(f"[{n}]" for n in nums)).encode())
            last = end
        pieces.append(data[last:])
        out.append(b"".join(pieces).decode("utf-8"))
    return "".join(out)


def _doc_key(ctx: Any) -> str | None:
    for m in getattr(ctx, "custom_metadata", None) or []:
        if m.key == "doc" and m.string_value:
            return str(m.string_value)
    return None


def answer_from_response(response: types.GenerateContentResponse, model: str) -> Answer:
    candidate = response.candidates[0] if response.candidates else None
    if candidate is None:
        feedback = response.prompt_feedback
        reason = getattr(feedback.block_reason, "value", None) if feedback else None
        raise RagError(
            f"Gemini blocked the question ({reason})" if reason else "Gemini returned no answer"
        )
    parts = _parts_text(candidate)
    text = "".join(parts).strip()
    if not text:
        reason = getattr(candidate.finish_reason, "value", candidate.finish_reason)
        raise RagError(f"Gemini returned no answer (finish reason: {reason or 'unknown'})")
    gm = candidate.grounding_metadata
    chunks = list(gm.grounding_chunks or []) if gm else []
    supports = list(gm.grounding_supports or []) if gm else []
    queries = list(gm.retrieval_queries or []) if gm else []

    retrieved: list[tuple[int, types.GroundingChunkRetrievedContext]] = [
        (i, c.retrieved_context) for i, c in enumerate(chunks) if c.retrieved_context
    ]
    by_chunk = dict(retrieved)

    # Number sources by first citation; identical passages share a number.
    numbers: dict[int, int] = {}
    key_to_number: dict[tuple[Any, ...], int] = {}
    sources: list[Source] = []

    def number_for(i: int, cited: bool = True) -> int | None:
        if i in numbers:
            return numbers[i]
        ctx = by_chunk.get(i)
        if ctx is None:
            return None
        key = (ctx.title, _page(ctx), (ctx.text or "").strip())
        if key not in key_to_number:
            key_to_number[key] = len(sources) + 1
            sources.append(
                Source(
                    number=key_to_number[key],
                    title=ctx.title or ctx.document_name or "Untitled",
                    text=(ctx.text or "").strip(),
                    page=_page(ctx),
                    engine_document_id=ctx.document_name,
                    doc_key=_doc_key(ctx),
                    cited=cited,
                )
            )
        numbers[i] = key_to_number[key]
        return numbers[i]

    marks: dict[tuple[int, int], list[int]] = {}
    for s in supports:
        seg = s.segment
        if seg is None or seg.end_index is None:
            continue
        nums = [n for i in (s.grounding_chunk_indices or []) if (n := number_for(i)) is not None]
        if not nums:
            continue
        slot = marks.setdefault((seg.part_index or 0, seg.end_index), [])
        slot.extend(n for n in dict.fromkeys(nums) if n not in slot)

    if not sources:  # no support links: still show what was retrieved
        for i, _ in retrieved:
            number_for(i, cited=False)

    cited = _insert_markers(parts, marks).strip() if marks else text
    grounded = bool(sources) and not is_not_found(text)
    return Answer(text, cited, sources if grounded else [], model, grounded, queries)
