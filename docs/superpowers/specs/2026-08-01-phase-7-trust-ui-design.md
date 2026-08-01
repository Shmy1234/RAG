# Phase 7 Trust UI Design

## Goal

Wire the grounded-answer pipeline into the React chat experience so analysts can follow a live run, distinguish failures, and verify every citation against the exact filing passage. Improve lexical retrieval by removing a conservative set of filler words without changing the user's stored question, semantic query, or agent prompt.

## Scope

Phase 7 includes citation chips, an authenticated source-passage panel, durable citation rendering after reload, truthful pipeline status updates, explicit empty and error states, and retrieval-only query normalization. It does not redesign authentication, introduce background jobs, change the retrieval ranking algorithm, or add a frontend test framework.

## Architecture

The existing `POST /chat/stream` endpoint remains the single live-turn transport. The backend will begin the streaming response before orchestration and emit typed status data parts as retrieval, answer generation, grounding validation, and persistence begin. The final answer continues to use AI SDK text parts and includes typed citation data parts.

The frontend will parse those stream parts into focused presentation components. Citation metadata is also persisted in assistant `message_data`, allowing the same citation chips to be reconstructed from message history. Selecting a citation opens one source panel; the panel loads the authoritative passage through an authenticated FastAPI endpoint rather than accessing Supabase directly.

Retrieval normalization is isolated behind a pure backend function. The original question is used for persistence, semantic embedding, and the PydanticAI prompt. Only the Postgres full-text-search query receives the normalized text.

## Backend Components

### Turn progress events

The chat orchestration boundary will expose these stable stages:

- `searching`: searching the filing corpus.
- `analyzing`: generating an answer from retrieved evidence.
- `validating`: checking that every citation maps to retrieved evidence.
- `saving`: persisting the grounded answer and citations.

Each stage has fixed user-facing copy owned by the frontend. The backend sends identifiers, not prose, so wording can change without altering the protocol. The stream generator starts orchestration and emits a status event immediately before each stage's work. It then emits answer text, citation metadata, and the normal finish event. Status events must represent work that has actually started; the frontend must not guess pipeline progress from timers.

If orchestration fails after streaming has begun, the generator emits a typed error data part and closes cleanly. Error codes distinguish `retrieval_failed`, `grounding_failed`, and `processing_failed`. Authentication, authorization, malformed requests, and missing threads continue to fail as normal HTTP responses because those checks happen before the stream starts.

### Citation persistence and history

Every citation exposed to the frontend contains:

- `chunk_id`
- `citation_index`
- `citation_label`
- `location_label`
- `quoted_text`

The assistant message stores this metadata in `message_data.citations`. The history response already includes `message_data`; the frontend validates this untrusted JSON conservatively and ignores malformed citations instead of failing the whole thread.

### Source passage endpoint

Add an authenticated endpoint keyed by message and citation index, for example:

`GET /chat/messages/{message_id}/citations/{citation_index}/source`

The store first verifies that the message belongs to a thread owned by the authenticated user. It then joins the persisted citation to its document chunk and source document and returns:

- citation identity and stored quote
- full chunk text
- company name or ticker when available
- filing type and filing date
- page number and section heading when available
- source URL when the corpus contains one

Missing citations return `404`; citations belonging to another user's thread return `403`. The browser never queries privileged Supabase tables directly.

## Retrieval-Only Filler-Word Normalization

Create a small pure function in the retrieval package that tokenizes with Python's standard library and removes only a reviewed set of conversational filler terms. No NLTK or other runtime dependency is added.

The function must preserve:

- negations such as `no`, `not`, `without`, and `excluding`
- numbers, percentages, fiscal periods, and years
- ticker-like uppercase tokens
- finance and filing vocabulary
- meaningful comparison and direction terms such as `increase`, `decrease`, `versus`, and `from`

Normalization applies only to the lexical query. If every token would be removed, lexical retrieval receives the original trimmed question. Semantic embedding and the agent always receive the original question.

Unit tests cover representative conversational questions, negation, finance terms, numbers, and the all-filtered fallback.

## Frontend Components

Split the current monolithic message rendering into focused components:

- `AssistantMessage` renders answer text and citation chips.
- `CitationChip` displays the citation label and location and reports selection.
- `SourcePassagePanel` loads and displays one selected citation with loading, error, close, and external-source states.
- `RunStatus` renders the current server-reported stage with an accessible live region.
- `ChatEmptyState` distinguishes no selected thread, an empty thread, and no corpus match.
- `ChatError` maps typed transport failures to concise recovery guidance.

The source panel appears beside the conversation on wide screens and as an overlay or stacked panel on narrow screens. Only one citation is selected at a time. Closing the panel returns focus to the citation that opened it.

While a turn runs, the composer is disabled and `RunStatus` displays the latest status event. Status disappears when the run finishes or fails. Existing completed messages remain readable during a new run.

## Empty and Error States

Required empty states:

- no threads: invite the user to create a chat
- thread with no messages: prompt for a filing question
- grounded insufficient-evidence answer: render the answer normally with a clear no-match treatment and no fabricated citation controls

Required error handling:

- expired authentication: prompt the user to sign in again
- network or CORS failure: explain that the backend could not be reached and allow retry by preserving the draft
- retrieval failure: state that filing search failed
- grounding failure: state that the answer was withheld because its evidence could not be verified
- generic processing failure: provide a neutral retry message
- source passage failure: keep the conversation intact and show the error only inside the source panel

No raw backend exception text or stack details are shown to users.

## Data Flow

1. The user submits the original text.
2. FastAPI authenticates the user and verifies thread ownership.
3. The streaming response starts and emits `searching`.
4. Semantic retrieval embeds the original text; lexical retrieval uses the normalized text.
5. The stream emits `analyzing` before agent generation.
6. The stream emits `validating` before fail-closed citation validation.
7. The stream emits `saving` before persisting the assistant message and citations.
8. The stream emits answer text, citation metadata, and finish events.
9. The frontend renders chips from live citation data; reloaded threads reconstruct the same chips from `message_data.citations`.
10. Selecting a chip fetches its exact persisted source through the authenticated source endpoint.

## Testing and Verification

Backend pytest coverage must verify normalization, stage ordering, typed streamed failures, citation ownership checks, source response metadata, and `404`/`403` behavior. Existing offline tests remain network- and database-free by mocking at store and retrieval boundaries.

The frontend follows the repository's no-frontend-tests rule. Verification consists of `pnpm tsc --noEmit`, `pnpm lint`, `pnpm build`, and manual browser checks for live statuses, citation selection, passage loading, reload persistence, responsive layout, keyboard focus, empty states, and each mapped error state.

## Acceptance Criteria

- A submitted question displays truthful stage updates before the answer is available.
- The original question remains unchanged in chat history, semantic retrieval, and the agent prompt.
- Filler-word removal affects only full-text retrieval and introduces no dependency.
- Every valid live or historical citation renders as a chip with filing and location context.
- Clicking a citation shows the exact persisted quote and underlying chunk from the cited filing.
- One user's citation source cannot be read through another user's message id.
- Grounding failures never display an unverified answer.
- Empty, authentication, network/CORS, retrieval, grounding, and source-panel failures have distinct UI states.
- Type checking, linting, frontend build, and backend fast tests pass.
