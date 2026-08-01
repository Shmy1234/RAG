# Citation Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make citation clicks select the existing evidence rail and render cited source text with immediate neighboring chunks and content-aware GFM tables.

**Architecture:** Extend the existing citation-source API response with ordered neighboring chunks fetched from the same document. Keep `ChatThread` as the single selection owner. Render source chunks in `EvidencePanel` through `react-markdown` and `remark-gfm`, highlighting the cited quote in the center chunk.

**Tech Stack:** FastAPI, Supabase query client, React, TypeScript, `react-markdown`, `remark-gfm`, Tailwind.

## Global Constraints

- Use the locked Python + FastAPI backend and Vite + React frontend.
- Use existing dependencies; do not add a package.
- Do not add frontend test files; verify with TypeScript, lint, backend tests, and manual browser inspection.
- Preserve user/message authorization and the existing external “Open filing” new-tab behavior.

### Task 1: Extend citation-source API with neighboring chunks

**Files:**
- Modify: `backend/app/database/chats.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/chat/schemas.py`
- Test: `backend/tests/api/test_chat.py`

- [x] Add a store query that selects the cited chunk’s document chunks ordered by `chunk_index`, then returns the cited row plus at most one previous and one next chunk.
- [x] Add response models for neighboring chunks with the text, chunk index, page, and section fields needed by the UI.
- [x] Include `previous_chunks` and `next_chunks` in the endpoint response while preserving existing citation fields.
- [x] Add/adjust API tests for ordered neighbors and missing boundary neighbors.
- [x] Run the focused backend test file and fix failures.

### Task 2: Render markdown-aware evidence context

**Files:**
- Modify: `frontend/src/lib/chat-api.ts`
- Modify: `frontend/src/components/chat/EvidencePanel.tsx`
- Modify: `frontend/src/components/chat/QuoteHighlight.tsx`

- [x] Add typed neighbor chunk fields to `CitationSource`.
- [x] Add a markdown renderer using `react-markdown` with `remarkGfm`, styling tables for readable overflow and borders.
- [x] Render previous chunks, the cited center chunk, and next chunks in order, using the existing quote highlight for the center chunk when possible.
- [x] Preserve plain prose as prose; only markdown table syntax becomes a table.
- [x] Keep the original filing link as the only `target="_blank"` action.
- [x] Run `pnpm tsc --noEmit` and `pnpm lint`.

### Task 3: Verify citation selection behavior

**Files:**
- Inspect/modify if needed: `frontend/src/components/chat/CitationChip.tsx`
- Inspect/modify if needed: `frontend/src/components/chat/AssistantMessage.tsx`
- Inspect/modify if needed: `frontend/src/components/chat/ChatThread.tsx`

- [x] Confirm citation chips use the in-app selection callback and do not navigate or open a tab.
- [x] If any citation is rendered as a link by the answer markdown, intercept its click and map its citation index to the same selection state.
- [x] Run frontend type-check and lint again after any interaction adjustment.
- [ ] Manually verify multiple citation clicks update the same right rail, the cited chunk is highlighted, neighbors appear, and valid GFM tables render.

### Task 4: Final verification

- [x] Run the relevant backend tests.
- [x] Run `pnpm tsc --noEmit` and `pnpm lint` from `frontend`.
- [x] Run `git diff --check` and inspect the final diff for unrelated changes.
