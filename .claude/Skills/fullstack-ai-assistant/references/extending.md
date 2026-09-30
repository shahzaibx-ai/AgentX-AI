# Extending the project

Recipes for the requests that usually follow a first delivery. Each keeps the
existing layering: SDK details in providers, orchestration in services, thin
routes, and UI state in hooks.

## Server-side chat history (database)

1. API: add SQLModel/SQLAlchemy + Alembic (`uv add sqlmodel alembic`).
   Tables: `conversation(id, user_id, title, created_at, updated_at)`,
   `message(id, conversation_id, role, content, provider, model, created_at, feedback)`.
2. Routes: `GET/POST /api/conversations`, `GET/PATCH/DELETE /api/conversations/{id}`.
   Accept an optional `conversation_id` on `POST /api/chat`; persist the user
   message before streaming and the assistant message on `done`.
3. Web: replace the localStorage effects in `hooks/use-chat.ts` with fetches
   (keep the same public return shape so components don't change). Consider
   optimistic updates for rename/delete.

## Authentication

- Web: Auth.js (NextAuth) or Clerk. Replace `APP_CONFIG.user` with the session
  user in `AppSidebar` and `EmptyState`.
- API: a `get_current_user` dependency that verifies a JWT (or a shared secret
  header added by a Next.js route handler proxy). Add it to `chat` and `models`
  routes. With auth, switch the rewrite to a route handler so the server can
  attach the token.

## File attachments / vision

- Composer: add an attach button and drag-and-drop (the original HTML prototype
  had this). Send files as `multipart/form-data` to a new `/api/files` route, or
  base64 images inline.
- Schema: extend `ChatMessage.content` to `str | list[ContentPart]`.
- Providers: Ollama takes `images=[base64]` on a message; OpenAI-compatible
  APIs take `{"type":"image_url"}` parts; Anthropic takes `{"type":"image"}`
  blocks. Convert per provider inside `stream_chat`.

## Per-chat settings

Add `system_prompt` and `temperature` to the conversation, send them with each
request (`ChatRequest.temperature` already exists; add `system` handling by
sending a `system` message, which the service respects instead of the default).

## RAG / tools

Add a `services/retrieval.py` that augments `messages` before
`ChatService.stream()`; keep providers unaware of retrieval. For tool calling,
extend the `Provider` interface with an optional `stream_chat_with_tools` and
emit new SSE event types (`tool_call`, `tool_result`); the client parser
ignores unknown events, so older UIs keep working.

## Reasoning / thinking models

Ollama's `chat(..., think=True)` and some cloud models return separate
reasoning text. Emit it as `event: reasoning` with `{"delta": ...}` and render
a collapsible "Thinking" block in `message.tsx`. Don't mix it into `content`.

## Observability

Log `provider`, `model`, latency to first token, total tokens (Ollama returns
`eval_count`; OpenAI `stream_options={"include_usage": True}`; Anthropic
`message_delta.usage`) from `ChatService`. Add an `event: usage` if the UI
should show it.
