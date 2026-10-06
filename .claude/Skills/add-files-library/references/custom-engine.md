# A self-hosted engine (LangChain/LangGraph, Ollama, pgvector or Qdrant)

Replace Gemini File Search by writing a class that satisfies `RagEngine`
(`app/library/engine.py`) and selecting it in `build_engine`. The service, the
routes and the UI don't change: the chat stream, `/api/library/config` and the
privacy line under the composer use the engine's own `name`, `label`, `local`
and `model`. Everything private stays on your machines.

```
add_document: parse (pypdf/python-docx/text) → chunk (RAG_CHUNK_TOKENS/OVERLAP)
              → OllamaEmbeddings (e.g. nomic-embed-text, embeddinggemma) → vector store
              rows: text + metadata {scope, doc, title, page, engine_doc}
stream:       metadata filter → vector search (top_k) → [optional LangGraph: grade,
              rewrite query, retry] → ChatOllama answer with numbered passages → [n]
```

## 1. Settings and selection

```python
# settings.py
rag_engine: Literal["", "gemini", "offline", "langgraph"] = ""
rag_ollama_model: str = "llama3.2"              # answers
rag_ollama_embedding_model: str = "nomic-embed-text"
rag_vector_store: Literal["pgvector", "qdrant"] = "pgvector"
rag_database_url: SecretStr | None = None        # postgresql+psycopg://… or http://qdrant:6333

# __init__.py, build_engine
if name == "langgraph":
    from .langgraph_engine import LangGraphEngine
    return LangGraphEngine.from_settings(settings)
```

Packages (check current versions first): `langchain-ollama` (`ChatOllama`,
`OllamaEmbeddings`), `langgraph`, and `langchain-postgres` (`PGEngine`,
`PGVectorStore`) or `langchain-qdrant` (`QdrantVectorStore`) with
`qdrant-client`. Add them as an optional dependency group so Gemini-only
deployments stay small.

## 2. The methods

| Method | What to do |
|---|---|
| `name`, `label`, `local`, `model` | `"langgraph"`, `"Library search (Ollama)"`, `True`, the Ollama chat model id. `label` is shown to people; `local=True` makes the UI say questions stay on your servers |
| `ensure_store(name)` | create the table/collection if missing (embedding size from one test embedding); return its name |
| `store_info(id)` | count distinct `doc` values and rows; `embedding_model` = the Ollama model; None if missing |
| `add_document(store, path, title, mime_type, metadata)` | extract text **per page** (keep page numbers), split with `RecursiveCharacterTextSplitter` sized from `RAG_CHUNK_TOKENS`/`OVERLAP` (≈4 chars/token), embed in batches, insert with metadata `{**metadata, "title", "page", "engine_doc": <new uuid>}`; return that uuid. No text → `IndexingError("No text could be extracted …")`. Ollama down → `IndexingError` with a readable message |
| `delete_document(engine_doc_id)` | delete rows where `engine_doc = id` (missing is fine) |
| `purge(store, doc_key)` | delete rows where `doc = doc_key`; return the number of documents removed |
| `stream(turns, store_ids, metadata_filter)` | below |

All blocking work (parsing, embedding, DB calls) goes through
`asyncio.to_thread` or async clients; never block the event loop.

## 3. The filter

The service builds the filter itself, only from ids it looked up, in a small
AIP-160 subset: `key="value"` clauses joined by `OR`, optionally wrapped in
parentheses, e.g. `(scope="c:5f…" OR doc="9a…")`. Parse exactly that (reject
anything else with `RagError`) and translate:

- pgvector: `WHERE (metadata->>'scope' = ANY(:scopes) OR metadata->>'doc' = ANY(:docs))`
  with bound parameters, never string formatting. `PGVectorStore` accepts a
  filter dict like `{"$or": [{"scope": {"$in": scopes}}, {"doc": {"$in": docs}}]}`.
- Qdrant: `Filter(should=[FieldCondition(key="metadata.scope", match=MatchAny(any=scopes)),
  FieldCondition(key="metadata.doc", match=MatchAny(any=docs))])`; create payload
  indexes on `metadata.scope` and `metadata.doc`.

An empty or missing filter must never mean "search everything" in chat; the
service always passes one.

## 4. Answering with citations

1. Query = the last user turn; for follow-ups, condense with the history first
   (one short LLM call: "rewrite as a standalone question").
2. Retrieve `top_k` chunks with scores. Drop weak ones (tune a threshold on your
   data with the Retrieval test page). None left → yield one `Answer(text=NOT_FOUND,
   cited_text=NOT_FOUND, sources=[], grounded=False, model=…)` and stop.
3. Prompt the model with numbered passages and the rule: answer only from them,
   put `[n]` after each claim, and reply exactly `NOT_FOUND` otherwise.
4. Stream `Delta(text)` as tokens arrive (`ChatOllama.astream`).
5. Build the final `Answer`: keep only `[n]` markers that point at real
   passages, renumber them 1..k in order of first use, and return `Source`s
   (`title`, `text`, `page`, `engine_document_id=engine_doc`, `doc_key=doc`,
   `cited=True`). `grounded = bool(sources) and not is_not_found(text)`.
   `cited_text` carries the markers; `text` is the plain answer.

**Agentic RAG with LangGraph:** model step 2–4 as a graph: `retrieve → grade
(relevant?) → [rewrite query → retrieve] (max 2 loops) → generate → check
(every claim cited?)`. Keep the graph inside `stream`; the rest of the app
only sees `Delta`s and one `Answer`.

## 5. Tests and switching

- Unit-test the filter parser and the citation renumbering without network.
- Integration: run `tests/test_library.py` against your engine. Its `client`
  fixture builds the offline engine; add a parametrised fixture that passes
  `library_engine=YourEngine(fake_embeddings, fake_llm)` to `make_client`.
  LangChain has fake embeddings/chat models for this. A few tests assert the
  offline engine's label and model; skip those for yours.
- Switch: set `RAG_ENGINE=langgraph`, restart. Documents indexed by Gemini
  are re-queued automatically and re-indexed from the stored originals; watch
  Library → Overview until the queue is empty. To go back, switch again.
- Compare quality on the Retrieval test page with the same questions on both
  engines before switching production.
