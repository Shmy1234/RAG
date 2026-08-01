# Phase 6 Agent And Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the retrieval prerequisite and build a typed, fail-closed document agent that returns grounded answers, streams them through the existing chat endpoint, and persists citations.

**Architecture:** Finish `DocumentRetriever` first, then keep retrieval, PydanticAI, grounding, chat orchestration, streaming, and persistence behind focused interfaces. The agent receives explicit runtime dependencies and returns a `GroundedAnswer`; citation validation accepts only citations whose chunk ids are present in the current retrieved passages. The chat route owns authentication/thread access and delegates the turn to an orchestrator.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, PydanticAI, OpenAI, SQLAlchemy models, Supabase client, pytest.

## Global Constraints

- Use the locked FastAPI, Supabase Postgres, OpenAI, PydanticAI, and SQLAlchemy stack.
- Do not add runtime dependencies.
- Do not call `os.getenv`, `os.environ`, or `load_dotenv` in application modules; use `app.config.settings`.
- Fast tests must not call OpenAI, Supabase, or a real database.
- The agent may answer only from retrieved passages and must refuse unsupported questions clearly.
- Every successful factual answer must contain at least one valid citation; invalid or missing citations fail closed.
- Keep service-role credentials and retrieval/LLM calls on the backend.
- Preserve the existing AI SDK request shape and plain streaming response compatibility while adding structured citation metadata.

## Files

- Complete `backend/app/retrieval/retriever.py` and `backend/tests/retrieval/test_retriever.py`.
- Create `backend/app/assistant/instructions.md`, `deps.py`, `outputs.py`, `agent.py` and focused tests.
- Create `backend/app/grounding/validator.py` and focused tests.
- Create `backend/app/chat/orchestrator.py`, `streaming.py` and focused tests.
- Extend `backend/app/database/chats.py` with citation persistence and test it.
- Modify `backend/app/api/chat.py` to use the orchestrator, preserving auth and thread checks.
- Add optional integration verification and update only Phase 6 in `docs/todos.md` after verification.

## Task 1: Finish Retrieval Orchestration

- [x] Write the failing orchestration test for embedding, both ranked searches, RRF, and neighbors.
- [x] Run `cd backend && uv run pytest tests/retrieval/test_retriever.py -q`; confirm import failure.
- [x] Implement `DocumentRetriever.retrieve(...)` using the existing query helpers and `asyncio.to_thread` for synchronous SQLAlchemy work so request handlers do not block the event loop.
- [x] Export `DocumentRetriever` from `app.retrieval`.
- [x] Run the focused retrieval tests and commit `feat: add document retriever orchestration`.

## Task 2: Typed Agent Contract

- [x] Add `assistant/instructions.md` containing the explicit evidence, citation, refusal, and no-investment-advice contract.
- [x] Add `Citation` and `GroundedAnswer` Pydantic models. `Citation` must carry `chunk_id`, `citation_index`, `quoted_text`, `citation_label`, and `location_label`.
- [x] Add `DocumentAgentDeps` with `user_id`, `thread_id`, `retriever`, and `grounding_validator`.
- [x] Test citation serialization and answer shape before implementation.
- [x] Implement `assistant/agent.py` with `Agent(..., deps_type=DocumentAgentDeps, output_type=GroundedAnswer)` and bounded tools:
  `search_filings(query, top_k=5)`, `read_chunk(chunk_id)`, and `read_surrounding_chunks(chunk_id, window=1)`.
- [x] Tools must return typed Pydantic objects or a concise agent-readable “not found” result; no tool may execute arbitrary SQL.
- [x] Test the agent with PydanticAI’s local test model, asserting tool registration and typed output without network calls.
- [x] Commit `feat: add typed document agent`.

## Task 3: Fail-Closed Grounding

- [x] Write tests for valid citations, unknown chunk ids, quoted text not matching the passage, missing citations on a factual answer, and an explicit insufficient-evidence answer.
- [x] Implement `GroundingValidator.validate(answer, passages) -> GroundedAnswer` keyed by UUID, requiring every citation to map to a retrieved center or neighbor chunk and requiring `quoted_text` to occur in the mapped chunk text.
- [x] Permit zero citations only when the answer explicitly states that the corpus lacks sufficient evidence; otherwise raise a typed `GroundingError`.
- [x] Commit `feat: enforce grounded citations`.

## Task 4: Chat Orchestration And Persistence

- [x] Add an orchestrator test with fake retriever, fake agent runner, validator, and chat store.
- [x] Implement `run_chat_turn(...)`: append the user message, run the agent with explicit deps, validate the result, append the assistant message with serialized answer/citations, and persist one `message_citations` row per citation only after validation succeeds.
- [x] Ensure grounding failure persists no assistant answer or citations and propagates a controlled error.
- [x] Add `ChatStore.append_citations(...)` using the existing Supabase client and `asyncio.to_thread`.
- [x] Commit `feat: orchestrate grounded chat turns`.

## Task 5: Streaming Contract And Route Wiring

- [x] Write streaming tests for text deltas, a final citation metadata part, and controlled grounding failures.
- [x] Implement `chat/streaming.py` with an async generator that emits AI SDK UI message stream records for text and citation data.
- [x] Replace the stub path in `POST /chat/stream` with the orchestrator and stream only after the authenticated thread check.
- [x] Preserve existing 401, 403, and 404 behavior and retain the current `latest_user_text` parsing.
- [x] Run API tests and update the frontend to `DefaultChatTransport`.

## Task 6: Verification And Todos

- [ ] Add a skipped-by-default integration smoke test guarded by `@pytest.mark.integration` and `RUN_RETRIEVAL_INTEGRATION=1`.
- [x] Run `cd backend && uv run pytest -m 'not integration' -q`.
- [x] Run `cd backend && uv run ruff check app tests`.
- [ ] Run the optional live query/agent verification only when credentials and corpus are available.
- [ ] Mark Phase 6 checklist items complete only for verified behavior; leave live verification unchecked when it was not run.
- [ ] Review `git diff --check`, inspect the complete diff, and commit `chore: verify phase 6 agent grounding`.

## Phase 6 Public Interfaces

```python
class GroundingValidator(Protocol):
    def validate(
        self,
        answer: GroundedAnswer,
        passages: Sequence[SourcePassage],
    ) -> GroundedAnswer: ...


async def run_chat_turn(
    *,
    user_id: UUID,
    thread_id: UUID,
    user_text: str,
    store: ChatStore,
    agent_runner: AgentRunner,
    retriever: DocumentRetriever,
    grounding_validator: GroundingValidator,
) -> GroundedAnswer: ...
```

## Self-Review

- Retrieval remains independent from PydanticAI and uses pgvector + Postgres FTS + Python RRF.
- Agent tools are bounded and typed; arbitrary SQL and unbounded context are excluded.
- Grounding is enforced after generation and before assistant persistence or streaming.
- Unit tests remain offline; integration tests are explicitly marked and skipped by default.
