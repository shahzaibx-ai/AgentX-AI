# Security and privacy

- **Owner access:** `LIBRARY_TOKEN` (Bearer, constant-time compare) guards
  `/api/library/*` except `config`. Unset: open in development, 403 in
  production. A deploy without `ENVIRONMENT=production` and without a token is
  open, so set both. The web app keeps the token in `sessionStorage` (this tab).
- **No accounts yet:** every collection with documents can be searched, and its
  cited originals opened, by anyone who can use the chat. Keep confidential
  documents out until you add sign-in and per-collection access (check the
  user in `resolve_scope` and in `/files/{id}/content`).
- **Chat files** are reachable only by their random 128-bit id; questions may
  only search files of the request's `chat_id`. Library document ids are never
  accepted as chat files.
- **Filters** are built server-side from looked-up ids with escaped literals;
  client text never reaches the filter.
- **Serving uploads:** HTML, SVG, Office files etc. download as attachments; only
  PDF and plain text open inline, with `nosniff` and `Content-Security-Policy:
  sandbox; default-src 'none'`. Never relax this: an uploaded HTML file would
  run on your origin.
- **Storage:** names are `<id><allow-listed ext>` (no traversal). Uploads stream
  to a temp file with a size cap; the body-size middleware stops oversized
  requests early.
- **Markdown:** answers render without raw HTML; `[n]` links only become
  buttons for real source numbers.
- **Where data goes:** with Gemini, files and questions go to Google (the line
  under the composer says so); Google deletes raw uploads after 48 h but keeps
  the index until you delete the document. The offline and self-hosted engines
  keep everything local.
- **Retention:** chat files are deleted `CHAT_FILE_RETENTION_DAYS` (30) after
  they were last cited, and when their chat is deleted. Back up
  `LIBRARY_DATA_DIR`; the index can be rebuilt by re-indexing.
- **Abuse:** add rate limits on `/api/files` and `/api/chat` before exposing
  the app publicly; indexing and answering cost money on Gemini.
