# Adaptive Chat Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route chat prompts through instant, direct, quick-RAG, or deep-RAG execution so trivial and non-document questions return quickly while document research retains fail-closed grounding.

**Architecture:** A backend-owned hybrid router handles a tiny deterministic instant allowlist, then uses one typed fast-model call that either returns a direct answer or selects a RAG lane. Quick RAG performs one retrieval and one tool-free fast-model answer; deep RAG retains agentic retrieval with a larger budget. The orchestrator persists a common `GroundedAnswer`, route, and timing metadata through the existing SSE endpoint.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, PydanticAI 2.18, OpenAI, pytest, React, TypeScript, AI SDK SSE.

## Global Constraints

- Keep the locked FastAPI, React SPA, Supabase Postgres, pgvector/full-text, Supabase Auth, Railway, and OpenAI stack.
- Add no runtime dependency.
- All environment reads remain in `backend/app/config.py`.
- The backend offline test suite must make no network or database calls.
- Do not add frontend tests; verify with TypeScript compilation, lint, and a manual browser check when credentials are available.
- Routing is server-owned; ambiguous or evidence-sensitive prompts escalate to RAG.
- Every RAG answer passes the existing fail-closed `GroundingValidator` before persistence.

---

## File Structure

- Create `backend/app/chat/routing.py`: route types, instant matcher, routing decision validation, production fast-model router.
- Create `backend/app/chat/quick_rag.py`: exactly-one-search execution and tool-free fast grounded-answer model.
- Create `backend/tests/chat/test_routing.py`: deterministic and typed router behavior.
- Create `backend/tests/chat/test_quick_rag.py`: quick-RAG call counts, evidence, and failures.
- Modify `backend/app/config.py`, `backend/.env.example`, `backend/tests/conftest.py`, `backend/tests/test_config.py`: fast-model configuration.
- Modify `backend/app/assistant/agent.py`, `backend/app/assistant/instructions.md`, `backend/tests/assistant/test_agent.py`: enable bounded multi-step deep retrieval.
- Modify `backend/app/chat/orchestrator.py`, `backend/tests/chat/test_orchestrator.py`: route delegation, common persistence, timing metadata.
- Modify `backend/app/api/chat.py`, `backend/tests/api/test_chat.py`: dependency injection for router and quick runner.
- Modify `backend/app/chat/stages.py`, `backend/app/chat/streaming.py`, `backend/tests/chat/test_streaming.py`: truthful route-aware stages.
- Modify `frontend/src/lib/chat-api.ts`, `frontend/src/components/chat/RunStatus.tsx`: render the routing stage without assuming all later stages occur.

### Task 1: Fast-model configuration and hybrid router

**Files:**
- Create: `backend/app/chat/routing.py`
- Create: `backend/tests/chat/test_routing.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `ChatRoute = Literal["instant", "direct", "quick_rag", "deep_rag"]`.
- Produces: `RouteDecision(route: ChatRoute, answer: str | None)` with validation requiring an answer for `instant` and `direct`, and forbidding one for RAG routes.
- Produces: `ChatRouter.route(prompt: str) -> RouteDecision`.
- Produces: `instant_response(prompt: str) -> str | None`.
- Configures: required `OPENAI_FAST_MODEL: str` using the same `openai:<model>` validation as `OPENAI_CHAT_MODEL`.

- [ ] **Step 1: Write failing configuration and router tests**

Add tests proving `OPENAI_FAST_MODEL` is required and validated. In `test_routing.py`, use a fake runner to prove exact forms such as `"Hi!"`, `"hello"`, and `"thanks"` return deterministic replies without invoking the runner; near-matches such as `"Hi, summarize Apple's filing"` invoke it. Assert a single model result can return a `direct` answer, and malformed route/answer combinations raise Pydantic validation errors.

```python
def test_instant_prompt_skips_model_runner():
    runner = FakeRouteRunner(RouteDecision(route="deep_rag"))
    decision = asyncio.run(ChatRouter(runner).route("  Hi!  "))
    assert decision.route == "instant"
    assert decision.answer
    assert runner.calls == []

def test_non_instant_prompt_uses_one_typed_model_call():
    expected = RouteDecision(route="direct", answer="I can help explain how to use this workspace.")
    runner = FakeRouteRunner(expected)
    assert asyncio.run(ChatRouter(runner).route("What can you help me do?")) == expected
    assert runner.calls == ["What can you help me do?"]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend && uv run pytest tests/test_config.py tests/chat/test_routing.py -q`

Expected: failure because `OPENAI_FAST_MODEL`, `RouteDecision`, and `ChatRouter` do not exist.

- [ ] **Step 3: Implement the minimal router**

Use stdlib `re` for conservative prompt normalization. Instantiate a production PydanticAI routing agent with the fast model, `output_type=RouteDecision`, and instructions that reserve `direct` for conversation, app guidance, and transformations based only on supplied text. The instructions must explicitly send company, filing, business, financial, dated, comparative, citation, source-verification, and ambiguous factual requests to RAG. Call it with `UsageLimits(request_limit=1)`.

```python
class RouteDecision(BaseModel):
    route: ChatRoute
    answer: str | None = None

    @model_validator(mode="after")
    def require_route_appropriate_answer(self) -> "RouteDecision":
        needs_answer = self.route in {"instant", "direct"}
        if needs_answer != bool(self.answer and self.answer.strip()):
            raise ValueError("instant/direct routes require an answer; RAG routes forbid one")
        return self
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/test_config.py tests/chat/test_routing.py -q`

Expected: all focused tests pass with no network calls.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/chat/routing.py backend/tests/chat/test_routing.py backend/app/config.py backend/.env.example backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat: add adaptive chat router"
```

### Task 2: One-pass quick RAG

**Files:**
- Create: `backend/app/chat/quick_rag.py`
- Create: `backend/tests/chat/test_quick_rag.py`

**Interfaces:**
- Produces: `QuickRagRunner.run(prompt: str, *, retriever: DocumentRetriever, grounding_validator: GroundingValidator) -> GroundedAnswer`.
- Consumes: `DocumentRetriever.retrieve`, `DocumentAgentDeps.register_passage_evidence`, `AgentAnswer`, and `GroundingValidator.validate`.

- [ ] **Step 1: Write failing quick-RAG tests**

Use a fake retriever and fake answer runner. Assert one retrieval call with `top_k=5` and `candidate_k=50`, one model call containing registered evidence ids and quotes, canonical citations after validation, and no retrieval tool surface. Add an empty-result test that returns the standard insufficient-evidence answer without invoking the answer model. Add a failure test showing unsupported uncited output raises `GroundingError`.

```python
def test_quick_rag_retrieves_once_and_returns_validated_citation():
    retriever = FakeRetriever([passage()])
    model = EvidenceAnswerRunner()
    result = asyncio.run(
        QuickRagRunner(model).run(
            "What happened to Services revenue?",
            retriever=retriever,
            grounding_validator=GroundingValidator(),
        )
    )
    assert retriever.calls == 1
    assert model.calls == 1
    assert result.citations[0].chunk_id == passage().center.chunk.chunk_id
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend && uv run pytest tests/chat/test_quick_rag.py -q`

Expected: import failure because `quick_rag.py` does not exist.

- [ ] **Step 3: Implement minimal one-pass execution**

Create a dedicated tool-free PydanticAI agent using `OPENAI_FAST_MODEL`, `output_type=AgentAnswer`, one-request usage limits, and the existing citation rules. Serialize only the bounded `EvidenceCandidate` objects into the prompt. Build candidates through `DocumentAgentDeps` so quick and deep RAG share evidence registration and canonical validation.

```python
passages = await retriever.retrieve(prompt, top_k=5, candidate_k=50)
deps.add_passages(passages)
candidates = deps.register_passage_evidence(passages, prompt)
if not candidates:
    return GroundedAnswer(answer=INSUFFICIENT_EVIDENCE_ANSWER)
result = await self._answer_runner.run(build_quick_prompt(prompt, candidates), usage_limits=...)
return grounding_validator.validate(
    result.output,
    deps.retrieved_passages,
    evidence_candidates=deps.evidence_candidates,
)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/chat/test_quick_rag.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/chat/quick_rag.py backend/tests/chat/test_quick_rag.py
git commit -m "feat: add one-pass quick rag"
```

### Task 3: Bounded multi-step deep RAG

**Files:**
- Modify: `backend/app/assistant/agent.py`
- Modify: `backend/app/assistant/instructions.md`
- Modify: `backend/tests/assistant/test_agent.py`

**Interfaces:**
- Changes: `agent_usage_limits() -> UsageLimits` permits multiple distinct searches and contextual reads while remaining bounded.
- Changes: retrieval tools remain available after the first search in deep mode; identical searches continue to hit `DocumentAgentDeps.search_cache`.

- [ ] **Step 1: Replace the one-search-only tests with failing deep-retrieval tests**

Assert `search_filings` can be called for two distinct queries, increments the retriever twice, and reuses the cache for normalized duplicates. Assert `read_surrounding_chunks` remains callable after a search. Assert exact usage-limit values are bounded (`request_limit=6`, `tool_calls_limit=8`). Update the instruction contract test to require multiple searches only for comparisons, multi-part synthesis, or missing context.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/assistant/test_agent.py -q`

Expected: failure because tools are currently hidden after the first search and limits remain 4/6.

- [ ] **Step 3: Enable bounded deep tools**

Remove the global `retrieval_completed` tool-preparation gate from deep-agent tool registration. Keep duplicate-query caching, top-k caps, evidence registration, and typed retrieval errors. Update instructions so focused questions stop after one adequate search while complex comparisons may make distinct follow-up searches and contextual reads.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/assistant/test_agent.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/assistant/agent.py backend/app/assistant/instructions.md backend/tests/assistant/test_agent.py
git commit -m "feat: allow bounded deep retrieval"
```

### Task 4: Route-aware orchestration, persistence, and timing

**Files:**
- Modify: `backend/app/chat/orchestrator.py`
- Modify: `backend/tests/chat/test_orchestrator.py`

**Interfaces:**
- Changes: `run_chat_turn(..., router: ChatRouter, quick_rag_runner: QuickRagRunner, clock: Callable[[], float] = monotonic) -> GroundedAnswer`.
- Persists: assistant `message_data` with `route`, `routing_ms`, and `execution_ms`, all non-negative.
- Emits: `routing` for all lanes; `searching/analyzing/validating` only for RAG; `saving` for all lanes.

- [ ] **Step 1: Write route-specific failing orchestration tests**

Create separate tests for all four decisions. Assert instant/direct do not invoke retrieval, quick invokes only `QuickRagRunner`, deep invokes only the primary agent, RAG citations remain canonical, and every assistant persistence call contains route/timing metadata. Use an injected iterator-backed monotonic clock for stable timing assertions. Preserve the test that no assistant message is saved after grounding failure.

```python
assert store.grounded_calls[0][2] == {
    "phase": 8,
    "route": "instant",
    "routing_ms": 10,
    "execution_ms": 20,
    "citations": [],
}
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/chat/test_orchestrator.py -q`

Expected: failures because the orchestrator has no router or quick-RAG boundary.

- [ ] **Step 3: Refactor the orchestrator around route delegation**

Persist the user message, emit `routing`, time `router.route`, execute exactly one selected lane, validate deep output through the existing dependency evidence, emit `saving`, and persist the common answer with citations and metadata. Keep route branches small and move quick-RAG details to its module.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/chat/test_orchestrator.py -q`

Expected: all route and failure tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/app/chat/orchestrator.py backend/tests/chat/test_orchestrator.py
git commit -m "feat: orchestrate adaptive chat routes"
```

### Task 5: API injection and truthful streaming stages

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/chat/stages.py`
- Modify: `backend/app/chat/streaming.py`
- Modify: `backend/tests/api/test_chat.py`
- Modify: `backend/tests/chat/test_streaming.py`

**Interfaces:**
- Produces: `get_chat_router() -> ChatRouter` and `get_quick_rag_runner() -> QuickRagRunner` FastAPI dependencies.
- Changes: `Stage` includes `routing` and streaming accepts valid route-specific subsequences rather than enforcing a universal full sequence.

- [ ] **Step 1: Write failing API and streaming tests**

Update API overrides with fake router and quick runner. Add endpoint coverage for an instant prompt and a quick-RAG prompt. In streaming tests, assert `routing,saving` is valid for instant/direct and `routing,searching,analyzing,validating,saving` is emitted for RAG. Retain typed retrieval, grounding, processing, secrecy, and stream-opens-first assertions.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/api/test_chat.py tests/chat/test_streaming.py -q`

Expected: dependency/signature failures and an unknown `routing` stage.

- [ ] **Step 3: Wire production dependencies and stage types**

Construct the router and quick runner through focused FastAPI dependencies and pass them to `run_chat_turn`. Add `routing` to the backend stage literal. Keep the current error mapping and streaming queue; no client-supplied route is accepted.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/api/test_chat.py tests/chat/test_streaming.py -q`

Expected: all focused tests pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add backend/app/api/chat.py backend/app/chat/stages.py backend/app/chat/streaming.py backend/tests/api/test_chat.py backend/tests/chat/test_streaming.py
git commit -m "feat: stream adaptive chat routes"
```

### Task 6: Frontend routing status and full verification

**Files:**
- Modify: `frontend/src/lib/chat-api.ts`
- Modify: `frontend/src/components/chat/RunStatus.tsx`

**Interfaces:**
- Changes: `RunStage` includes `routing`.
- Changes: `RunStatus` renders only stages actually observed by the stream and labels routing as `Choosing the fastest answer path`.

- [ ] **Step 1: Update frontend stage typing and copy**

Prepend `routing` to `RUN_STAGES` and add its label. Keep stage rendering driven by streamed identifiers; direct routes must not display filing-search or citation-validation work.

- [ ] **Step 2: Run frontend static checks**

Run: `cd frontend && pnpm tsc --noEmit && pnpm lint`

Expected: both commands exit 0 with no errors.

- [ ] **Step 3: Run the full offline backend suite and Ruff**

Run: `cd backend && uv run pytest -m "not integration" -q && uv run ruff check app tests`

Expected: all offline tests pass and Ruff reports no violations.

- [ ] **Step 4: Run a production frontend build**

Run: `cd frontend && pnpm build`

Expected: Vite production build exits 0.

- [ ] **Step 5: Review the final diff and route requirements**

Run: `git diff --check && git status --short`

Confirm the final diff contains no unrelated `notes.txt` edits, no new dependency, no client route field, and route tests prove the intended external-call counts.

- [ ] **Step 6: Commit Task 6**

```bash
git add frontend/src/lib/chat-api.ts frontend/src/components/chat/RunStatus.tsx
git commit -m "feat: show adaptive routing status"
```
