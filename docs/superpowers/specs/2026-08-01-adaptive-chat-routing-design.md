# Adaptive Chat Routing Design

## Goal

Reduce perceived and end-to-end chat latency by routing each prompt through the least expensive path that can answer it safely, while preserving citation-backed answers for all SEC filing and company-fact questions.

## Scope

The feature introduces four server-selected chat routes:

- `instant`: deterministic responses for an intentionally small set of unmistakable conversational prompts.
- `direct`: one small-model call for non-document tasks that do not require external facts.
- `quick_rag`: one hybrid retrieval followed by one small-model grounded answer.
- `deep_rag`: agentic retrieval with multiple searches and optional surrounding-chunk reads, followed by grounded answer generation.

The existing authenticated `POST /chat/stream` endpoint remains the transport for every route. Thread ownership, message persistence, typed SSE events, citation rendering, and source inspection remain intact. The feature does not add client-controlled routing, a frontend test framework, speculative background jobs, or a new runtime dependency.

## Routing Architecture

Routing is server-owned and hybrid:

1. A deterministic instant matcher normalizes whitespace, case, and terminal punctuation and recognizes only an explicit allowlist of greetings, acknowledgements, thanks, and simple capability prompts. A match returns a fixed response without calling OpenAI or retrieval.
2. Every non-instant prompt is sent to the configured fast model through a typed routing call. The router returns `direct`, `quick_rag`, or `deep_rag`; when it selects `direct`, the same call also returns the final answer so a second model round trip is not required.
3. Routing instructions forbid `direct` for requests involving companies, filings, financial or business facts, figures, dates, comparisons, source verification, citations, or facts that could require corpus evidence. Ambiguous prompts route upward rather than downward.
4. The router selects `quick_rag` for focused document questions answerable with one search and `deep_rag` for comparisons, multi-part synthesis, longitudinal questions, broad summaries, or requests likely to require multiple searches or neighboring context.

The server does not trust a route supplied by the browser. The selected route is recorded in assistant `message_data` for observability.

## Route Execution

### Instant

The instant matcher owns a small mapping of normalized prompt forms to fixed concise responses. It must not generate factual company or filing content. The route persists the user message and an assistant message with no citations.

The stream may emit the fixed answer as soon as routing is complete instead of waiting for assistant-message persistence. Persistence still runs within the stream lifecycle. A persistence failure produces the existing typed processing failure and is logged; the client must not be told that saving succeeded when it did not.

### Direct

The typed fast-model routing result contains the direct answer. This lane is limited to conversation, product guidance, and transformations or explanations based entirely on text supplied by the user. It must refuse to produce uncited SEC, company, market, or other external factual claims. The answer is persisted without citations.

### Quick RAG

Quick RAG performs exactly one call to the existing `DocumentRetriever.retrieve` hybrid retrieval path. The original prompt remains the semantic query and agent input; the existing normalized text remains limited to lexical retrieval.

The fast model receives the bounded evidence candidates directly and returns the existing typed `AgentAnswer`. It has no retrieval tools, so it cannot initiate a second search or read neighboring chunks. The existing `GroundingValidator` validates every selected evidence id before persistence. Unsupported questions produce an explicit insufficient-evidence answer rather than an uncited guess.

### Deep RAG

Deep RAG uses the primary configured chat model and retrieval tools. It may run multiple distinct searches and may read a chunk or its surrounding chunks when the initial evidence lacks necessary context. Strict request and tool-call limits prevent unbounded work.

The current one-search cache remains useful for duplicate queries, but deep mode must not globally hide retrieval tools after the first search. It may reject exact duplicate reads and continue to register all retrieved evidence through `DocumentAgentDeps`. The final typed answer passes the same fail-closed grounding validator used by quick RAG.

## Components and Interfaces

- A focused routing module owns route literals, the deterministic matcher, the typed fast-model decision schema, and the router service.
- A focused quick-RAG runner owns the single retrieval call and fast grounded-answer call.
- `run_chat_turn` remains the orchestration entry point and delegates to route-specific execution rather than containing model prompt details.
- `DocumentAgentDeps` receives an explicit retrieval mode or budget used by tool preparation to distinguish quick and deep behavior.
- Configuration adds one required fast model setting. The existing `OPENAI_CHAT_MODEL` remains the deep model. Both settings use the existing `openai:` validation convention.
- The existing `GroundedAnswer` remains the common result passed to streaming. Direct and instant routes return it with empty citations and passages.
- Assistant `message_data` records at least `route` and server-side routing/execution durations. User content remains unchanged.

No database migration is required because `message_data` is already a JSON object and citation persistence already accepts an empty citation list.

## Streaming and Status

The stream adds a `routing` stage before route-specific work. RAG routes retain `searching`, `analyzing`, `validating`, and `saving`. Direct and instant routes omit stages that never occur and proceed from `routing` to `saving`.

The frontend displays status identifiers emitted by the backend rather than assuming every run contains the entire fixed sequence. It adds concise copy for routing while retaining current filing-search, analysis, validation, and saving labels.

Instant responses prioritize time to first visible text. Model-backed routes continue to emit stage events while work occurs. This change does not require token-level proxy streaming from OpenAI; answers may still arrive in the existing bounded SSE text chunks once each route has a validated result.

## Error Handling

- Router or fast-model failure becomes `processing_failed`; it does not silently fall back to an uncited direct answer.
- Retrieval failures in either RAG lane remain `retrieval_failed`.
- Citation or evidence validation failures remain `grounding_failed`.
- Persistence failures remain `processing_failed` and are logged server-side.
- Authentication, malformed input, missing threads, and forbidden threads continue to fail before the stream starts with their existing HTTP responses.
- An invalid or incomplete typed routing result is rejected at the model boundary.
- Ambiguity in content classification resolves to the more evidence-intensive route.

## Latency and Observability

The feature optimizes route work rather than promising environment-independent millisecond thresholds. Tests verify call counts and skipped dependencies; production timing data verifies real latency.

For each assistant response, `message_data` records the selected route plus routing and execution durations in milliseconds. Logs include the same route and timing fields without user prompt contents. These fields allow comparison of instant, direct, quick-RAG, and deep-RAG performance after deployment.

## Testing

Backend unit tests remain offline and mock only model, retrieval, and persistence boundaries.

Coverage must verify:

- every supported instant form returns the expected response without router, model-answer, or retrieval calls;
- near-matches and factual prompts do not enter the instant lane;
- a direct router result reuses the answer from the routing call and never invokes retrieval;
- company, filing, figures, comparisons, and ambiguous factual prompts are prohibited from direct routing by the instruction contract;
- quick RAG performs exactly one retrieval, cannot access retrieval tools, validates citations, and persists them;
- deep RAG permits multiple distinct searches and surrounding-chunk reads within configured usage limits;
- all four routes persist the user and assistant messages with the selected route metadata;
- route-specific stage sequences are truthful;
- retrieval, grounding, router, and persistence failures retain their typed error codes;
- timing metadata is present and non-negative using an injected monotonic clock where exact assertions are needed;
- existing citation source and ownership behavior remains unchanged.

Frontend verification uses TypeScript compilation, linting, and manual browser checks, consistent with repository policy. Manual checks cover each route's visible status, response, persisted reload state, and citation interaction for both RAG lanes.

## Acceptance Criteria

- Exact trivial conversational prompts receive a fixed response without OpenAI or retrieval.
- Slightly more complex non-document prompts use one fast-model call and no retrieval.
- Focused filing questions use one retrieval pass and a fast grounded-answer call.
- Complex document questions can use multiple searches and surrounding context with the primary model.
- SEC, company, and filing facts never receive uncited direct answers.
- Every RAG answer remains fail-closed under the existing citation validator.
- The selected route and timing metadata are persisted for every assistant answer.
- Streaming status reflects only work that actually occurs.
- The backend offline suite, frontend typecheck, and frontend lint remain clean.
