# Pilot readiness checks

Run this checklist against the same Supabase project and OpenAI configuration the
five pilot analysts will use. Record the date, commit SHA, browser, viewport,
model, and generated `pilot-smoke-report.json` with the pilot release notes.

## Automated preflight

```bash
cd backend
uv run pytest -m "not integration"
uv run ruff check .
RUN_RETRIEVAL_INTEGRATION=1 uv run pytest tests/integration/test_live_system.py

cd ../frontend
pnpm lint
pnpm build
```

The unit/API suite covers authentication rejection, per-user ownership, history
reload through a fresh HTTP client, 40 concurrent user identities, atomic message
positions, grounded persistence, all typed stream failures, and an immediate SSE
start event. The integration suite verifies the live migration revision, corpus,
embedding dimensions, atomic database functions, and retrieval quality fixtures.

## Ten-question smoke pass

```bash
cd backend
uv run python smoke_assistance.py --output pilot-smoke-report.json
```

For each result, review the answer and open at least one citation in the product.
Pass only when:

- the response addresses the question or explicitly identifies insufficient evidence;
- every factual claim is supported by the attached exact passage;
- company, filing, year, and location labels match the passage;
- question 10 does not turn correlation into a claim that generative AI caused margins;
- no result contains a processing, retrieval, or grounding failure.

The script's `first_stage_seconds` measures the live retrieval/model path reaching
the analyzing stage. The API emits the SSE start event immediately and searching
status after persisting the user's question. In browser network timing, treat a
start event over 3 seconds as a pilot blocker; record median and worst time across
the ten questions rather than relying on one warm request.

## Signed-in browser pass

Use a real pilot-style email account and a desktop viewport first:

1. Create a chat, send a question, and confirm searching → analyzing → validating
   → saving appears in order.
2. Collapse and reopen the sidebar. Search chat history and select the new thread.
3. Reload the page, then sign out and back in. Confirm the thread and both messages
   remain and another account cannot open the thread URL.
4. Hover a citation and compare the preview quote. Select it, verify the exact
   quote and neighboring chunks, close with Escape, and confirm focus returns to
   the citation chip.
5. Resize to 390 × 844. Open the navigation sheet and citation evidence sheet;
   confirm both close by button and Escape without horizontal overflow.
6. Exercise the visible error treatments: expired session (401), another user's or
   missing thread (403/404), stopped backend (network), retrieval failure,
   grounding rejection, and unexpected processing failure. Confirm raw exception
   text and credentials never appear in the browser.

Record pass/fail and a screenshot for each item. Restore the normal backend and
credentials after failure-state checks; do not leave intentionally broken pilot
configuration deployed.

## Scale assumptions for approximately 40 analysts

- The API is stateless; request identity comes from the verified bearer token.
- Every thread list/read/update/stream boundary applies the authenticated user id.
- Database RLS independently enforces ownership for threads, messages, and citations.
- Network and Supabase SDK calls on request paths are async or moved to worker threads.
- Atomic Postgres functions serialize message positions per thread, avoiding a
  process-local lock or a single-user counter.
- Retrieval uses bounded candidate/top-k results, and agent request/tool limits
  cap work per turn.

These properties support a 40-user pilot assumption; they are not a substitute
for load testing if usage becomes highly concurrent or the corpus grows materially.
