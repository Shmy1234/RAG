# Phase 7 Trust UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make grounded chat verifiable in the React app with live pipeline status, citation chips, source passages, durable history rendering, explicit errors, and lexical-only filler-word normalization.

**Architecture:** Keep FastAPI as the authority for retrieval, orchestration, persistence, and ownership checks. Extend the existing SSE/AI SDK stream with typed status, citation, and error data parts. Keep the original user query intact for storage, embeddings, and the agent; normalize only the full-text query. Add a backend source endpoint and focused frontend chat components.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy/Supabase, pytest; Vite, React 19, TypeScript, Tailwind, AI SDK.

## Global Constraints

- Do not add NLTK or any other runtime dependency.
- Use the original question for persistence, semantic retrieval, and the agent prompt.
- Apply normalization only to Postgres full-text search.
- Preserve existing HTTP auth/thread behavior and the AI SDK request shape.
- Frontend verification uses `pnpm tsc --noEmit`, `pnpm lint`, `pnpm build`, and manual browser checks; do not add frontend tests.
- Backend fast tests must not call OpenAI, Supabase, or a real database.

### Task 1: Lexical Query Normalization

**Files:** Create `backend/app/retrieval/normalization.py`; modify `backend/app/retrieval/queries.py`, `backend/app/retrieval/retriever.py`; test `backend/tests/retrieval/test_normalization.py` and existing query/retriever tests.

- [ ] Add failing tests for filler removal, preserved negation/finance terms/numbers/tickers, and all-filtered fallback.
- [ ] Implement `normalize_full_text_query(query: str) -> str` with stdlib tokenization and an explicit small allowlist of protected tokens.
- [ ] Pass normalized text only to `full_text_search`; leave embedding input unchanged.
- [ ] Run `cd backend && uv run pytest tests/retrieval -q`.

### Task 2: Stream Protocol and Real Progress

**Files:** Modify `backend/app/chat/orchestrator.py`, `backend/app/chat/streaming.py`, `backend/app/api/chat.py`; test `backend/tests/chat/test_streaming.py`, `backend/tests/chat/test_orchestrator.py`, and `backend/tests/api/test_chat.py`.

- [ ] Define typed stage/error payloads for `searching`, `analyzing`, `validating`, and `saving`.
- [ ] Refactor the turn boundary to accept an async progress callback and invoke it immediately before each corresponding operation.
- [ ] Start the response generator before orchestration and emit status, text, citation, finish, and typed error events in order.
- [ ] Ensure pre-stream auth/ownership failures remain HTTP errors and post-stream failures do not expose exception text.
- [ ] Run focused backend chat/API tests.

### Task 3: Source Passage Retrieval API

**Files:** Modify `backend/app/database/chats.py`, `backend/app/api/chat.py`, `backend/app/chat/schemas.py`; test `backend/tests/database/test_chats.py` and `backend/tests/api/test_chat.py`.

- [ ] Add a store method that verifies message ownership, loads the requested citation, and joins its chunk/document metadata.
- [ ] Add `GET /chat/messages/{message_id}/citations/{citation_index}/source` with typed response and `403`/`404` mapping.
- [ ] Return quote, full chunk, filing identity/location, and source URL.
- [ ] Run database/API tests and `cd backend && uv run ruff check app tests`.

### Task 4: Frontend Stream Data and API Types

**Files:** Modify `frontend/src/lib/chat-api.ts`, `frontend/src/lib/chat-stream.ts`, `frontend/src/components/chat/message-format.ts`; create `frontend/src/components/chat/chat-types.ts` if needed.

- [ ] Add strict citation/source/status/error types and a guarded parser for persisted `message_data.citations`.
- [ ] Preserve citation data when converting historical assistant messages to UI messages.
- [ ] Add `chatApi.getCitationSource(messageId, citationIndex)` using the shared API client.
- [ ] Map AI SDK data parts into renderable status, citation, and error state without `any`.

### Task 5: Trust UI Components and Chat Integration

**Files:** Create `frontend/src/components/chat/AssistantMessage.tsx`, `CitationChip.tsx`, `SourcePassagePanel.tsx`, `RunStatus.tsx`, `ChatError.tsx`; modify `frontend/src/components/chat/ChatThread.tsx`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/index.css` only when needed.

- [ ] Render assistant text with citation chips and one selected source panel.
- [ ] Load the exact source passage on chip selection, with loading/error/close states and focus restoration.
- [ ] Render live server status in an accessible live region and disable the composer while active.
- [ ] Add distinct no-thread, empty-thread, insufficient-evidence, auth, network/CORS, retrieval, grounding, generic, and source-panel states.
- [ ] Keep drafts on failed submission and keep existing messages visible.

### Task 6: Verification and Documentation

**Files:** Modify `docs/todos.md` only for verified checklist items and `README.md` only if the local verification workflow needs clarification.

- [ ] Run `cd backend && uv run pytest -m 'not integration' -q`.
- [ ] Run `cd frontend && pnpm tsc --noEmit`, `pnpm lint`, and `pnpm build`.
- [ ] Manually verify live statuses, citation selection, reload persistence, responsive source panel, keyboard focus, empty states, and failure states in the browser.
- [ ] Run `git diff --check` and inspect the complete diff; do not alter unrelated worktree changes.
