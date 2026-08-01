# Document Copilot — implementation checklist

Work top to bottom. Each phase unlocks the next. Check items off as you go.

## Where to start: backend, frontend, or both?

Start with foundation, then backend-led vertical slices.

| Order | Why |
| --- | --- |
| 1. Supabase + sample data | Everything persists here; you need a project and a corpus to test against. |
| 2. Backend schema + migrations | Auth, chat, retrieval, and citations all depend on the data model. |
| 3. Thin vertical slices | Wire auth, then a stubbed chat stream, then real RAG — each slice touches frontend + backend together. |
| 4. Frontend in parallel (lightly) | Scaffold the SPA early, but don't build citation UI or chat polish until the backend can return real grounded answers. |

The critical path is data model → ingestion → retrieval → LLM → citations. The frontend is mostly a streaming chat shell with auth and citation display — it shouldn't get far ahead of working APIs.

## Phase 0 — Prerequisites & foundation

- [x] Install toolchain: Python 3.12+, uv, Node 20+, pnpm (see README)
- [x] Create Supabase project and collect credentials (supabase-setup)
- [x] Create OpenAI API key (needed from Phase 6 onward)
- [ ] Set a real contact email in `USER_AGENT` in `data/download.py` before downloading:

  ```bash
  uv run data/download.py
  ```

- [x] Confirm `data/downloads/manifest.json` lists AAPL, MSFT, NVDA, AMZN, GOOGL filings (2021–2025)

## Phase 1 — Backend scaffold & database

Goal: a running FastAPI service with a migrated Supabase schema.

- [x] Init backend deps and project layout (backend-setup)
- [x] `app/config.py` — settings module, fail fast on missing env vars
- [x] `app/main.py` — FastAPI app, CORS, health check (`GET /health`)
- [x] SQLAlchemy models in `app/database/models/`:
  - [x] `users`
  - [x] `source_documents`
  - [x] `document_chunks` (embedding + generated tsvector)
  - [x] `chat_threads`
  - [x] `chat_messages`
  - [x] `message_citations`
- [x] Alembic init + first migration:
  - [x] `create extension if not exists vector`
  - [x] `vector(1536)` embedding column
  - [x] Generated `tsvector` column on chunks
  - [x] HNSW index (vector) + GIN index (full-text)
  - [x] RLS policies (users see only their own chats)
- [x] Run `uv run alembic upgrade head` against the replacement Supabase direct connection
- [x] `app/database/supabase.py` — user-scoped and service-role clients
- [x] Verify against the replacement environment: `uv run uvicorn app.main:app --reload` → health check returns 200

## Phase 2 — Auth (full stack)

Goal: analysts can sign in with email; backend rejects unauthenticated requests.

### Backend

- [x] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose `get_current_user`
- [x] Reject missing/expired tokens with 401 before any chat or retrieval work

### Frontend

- [x] Scaffold Vite + React + TypeScript + Tailwind + shadcn (frontend-setup)
- [x] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [x] `src/lib/supabase.ts` — browser Supabase client
- [x] `src/lib/http.ts` + `src/lib/api.ts` — fetch wrapper with automatic bearer token
- [x] Sign-in / sign-up pages (email only, no SSO)
- [x] Protected routes — redirect unauthenticated users to login
- [ ] Verify: sign up, sign in, token reaches backend on a test authenticated endpoint

## Phase 3 — Chat shell (vertical slice, stubbed)

Goal: end-to-end chat UI streaming from FastAPI, no real retrieval yet.

### Backend

- [x] Chat thread CRUD: list threads, create thread, load message history
- [x] `POST /chat/stream` — accepts AI SDK message format, streams a stubbed assistant reply
- [x] Persist user + assistant messages to `chat_messages` after stream completes
- [x] 403 when user accesses another user's thread

### Frontend

- [x] React Router: login, chat list, chat thread routes
- [x] AI SDK chat primitives pointed at `POST /chat/stream` with Supabase bearer token
- [x] Thread sidebar (past conversations)
- [x] Basic message list + input + streaming indicator
- [ ] Verify: create thread, send message, see streamed stub response, reload and see history

## Phase 4 — Ingestion pipeline

Goal: SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

- [x] `ingest/` scripts (or CLI entrypoint) for one-off corpus loading
- [x] HTML → normalized Markdown extraction with stable SEC item headings
- [x] Chunking strategy (size + overlap; store chunk index and available page/section metadata plus ticker, filing type, year)
- [x] Write `source_documents` rows with filing metadata from `manifest.json`
- [x] Write `document_chunks` rows with text + metadata
- [x] OpenAI embedding generation → store `vector(1536)` per chunk
- [x] Generated `tsvector` populated for full-text search
- [x] Idempotent re-run (skip already-ingested documents)
- [x] Unit tests: chunking logic, metadata extraction
- [x] Run ingestion on the replacement Supabase project (25 filings × 5 companies)
- [x] Verify replacement-project chunks; spot-check a known passage (e.g. Apple revenue mix table)

## Phase 5 — Retrieval

Goal: a user question returns ranked, relevant source passages.

- [x] `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- [x] `retrieval/queries.py` — Postgres full-text search over `search_vector`
- [x] `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `retrieval/retriever.py` — query → fused ranked passages + neighbor chunks
- [x] Unit tests: fusion ranking, query assembly (mock DB)
- [x] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus
- [x] Verify: test queries from client-brief return relevant chunks (manual or scripted)

## Phase 6 — LLM agent & grounding

Goal: grounded answers with enforced citations — the core product contract.

- [x] `assistant/instructions.md` — product contract (cite everything, refuse to invent, no stock picks)
- [x] PydanticAI agent with typed deps (`DocumentAgentDeps`) and output (`GroundedAnswer`)
- [x] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [x] `chat/orchestrator.py` — one turn: retrieve → agent → validate → stream → persist
- [x] `grounding/validator.py` — every citation maps to a retrieved passage; fail closed on violation
- [x] `chat/streaming.py` — AI SDK-compatible stream (text deltas + citation metadata parts)
- [x] Persist `message_citations` linked to assistant messages
- [x] Unit tests: citation validation, grounding enforcement, message conversion
- [ ] Verify against client-brief example questions:
  - [ ] Answers cite specific filings and pages
  - [ ] Under-specified questions get “not enough evidence” responses
  - [ ] Question 10 (generative AI margins) refuses to infer beyond filings

## Phase 7 — Trust UI (citations & source passages)

Goal: analysts can verify every claim in one click — this is what makes the product usable.

- [x] Citation chips/links on assistant messages (company, filing type, date, page/section)
- [x] Source passage panel — show underlying excerpt for selected citation
- [x] Empty states (no threads, no corpus match)
- [x] Error states (auth expired, retrieval failure, grounding failure, network/CORS)
- [x] Loading/streaming status during assistant run
- [ ] Verify: click a citation → see the exact passage from the filing

### Design system pass (see `specs/2026-08-01-phase-7-design-system-design.md`)

- [x] shadcn primitives installed; `components/ui` is generated, not hand-rolled
- [x] Collapsible icon-rail sidebar with grouped thread history and search
- [x] User menu with identity, theme switch, and sign-out
- [x] Threads titled from their first question (`PATCH /chat/threads/{id}`)
- [x] Backend `data-status` / `data-error` stream parts; status reflects real stages
- [x] Markdown answers with tables; auto-growing composer with stop control
- [x] Evidence rail highlights the cited quote inside its surrounding chunk
- [x] Dark mode (system default, manual override, no first-paint flash)
- [ ] Manual browser pass while signed in: sidebar collapse, mobile sheet, live stages,
      citation hover and selection, focus restoration, each error state

## Phase 8 — Pilot readiness

Goal: 5 senior analysts can use it for a week and report ≥3 hours saved per analyst per week.

- [x] README “Running locally” section — copy-paste commands for backend + frontend + env vars
- [x] Seed or document how to ingest/update the corpus
- [ ] Smoke-test all 10 example questions from the client brief
- [x] Confirm chat history persists across sessions
- [x] Confirm ~40-user scale assumptions (no hardcoded single-user shortcuts)
- [x] Basic structured logging on backend (`structlog`) for debugging failed turns
- [x] Review latency: streaming starts within a few seconds for typical queries

## Phase 9 — DevOps & deployment (AWS + Docker + GitHub Actions)

Goal: deploy the production app through a repeatable, observable pipeline while learning the AWS building blocks behind container hosting, networking, load balancing, health checks, and rollback.

Target architecture: Route 53 → CloudFront + S3 (React SPA) and Application Load Balancer → ECS Fargate (Dockerized FastAPI) → Supabase + OpenAI.

### 9.1 — AWS account, access, and infrastructure as code

- [ ] Enable MFA on the AWS root account; create an administrative IAM identity for setup work and stop using root
- [ ] Create an AWS Budget with email alerts and enable billing/free-tier usage notifications
- [ ] Choose one AWS region and document it as the deployment region
- [ ] Define the deployment infrastructure in AWS CloudFormation so it can be reviewed, recreated, and updated without console-only steps
- [ ] Store production secrets in AWS Secrets Manager and non-secret configuration in Systems Manager Parameter Store
- [ ] Create separate ECS task execution and application task IAM roles with least-privilege policies

### 9.2 — Docker images

- [ ] Add a production backend `Dockerfile`: pinned Python base image, dependency layer caching, non-root runtime user, Uvicorn command, and `.dockerignore`
- [ ] Add a Docker health check that calls the FastAPI health endpoint without depending on Supabase or OpenAI availability
- [ ] Build and run the backend image locally; verify health, CORS, authentication, streaming, and graceful shutdown
- [ ] Create a private Amazon ECR repository with immutable tags, vulnerability scanning, and a lifecycle rule for old images
- [ ] Tag backend images with the Git commit SHA instead of deploying mutable `latest` tags

### 9.3 — VPC and network security

- [ ] Create a VPC spanning two Availability Zones
- [ ] Create public subnets for the Application Load Balancer and NAT gateways
- [ ] Create private subnets for ECS tasks; route outbound Supabase, OpenAI, ECR, and CloudWatch traffic through the NAT gateways
- [ ] Create an ALB security group allowing public HTTP/HTTPS traffic
- [ ] Create an ECS security group allowing backend traffic only from the ALB security group
- [ ] Confirm the database remains in Supabase; do not add RDS or expose ECS task ports directly to the internet

### 9.4 — Backend on ECS Fargate

- [ ] Create an ECS cluster, Fargate task definition, and service using the ECR image
- [ ] Inject secrets and configuration into the task definition; set production `ALLOWED_ORIGINS` explicitly
- [ ] Send container logs to a CloudWatch Logs group with a retention policy
- [ ] Create an Application Load Balancer, HTTPS listener, target group, and HTTP-to-HTTPS redirect
- [ ] Configure the target group to health-check the FastAPI health endpoint with an appropriate startup grace period
- [ ] Run two ECS tasks across Availability Zones and enable rolling deployments
- [ ] Enable the ECS deployment circuit breaker with automatic rollback when tasks fail to start or become healthy
- [ ] Configure ECS Service Auto Scaling with conservative minimum/maximum task counts and CPU/memory targets
- [ ] Verify the ALB routes only to healthy tasks and the API stream remains open for a complete assistant response

### 9.5 — Frontend on S3 and CloudFront

- [ ] Create a private S3 bucket for the Vite production build; block all public bucket access
- [ ] Create a CloudFront distribution with Origin Access Control so only CloudFront can read the bucket
- [ ] Configure SPA fallback routing so React Router paths return `index.html`
- [ ] Configure production `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` at build time
- [ ] Set long-lived immutable caching for hashed assets and no-cache behavior for `index.html`
- [ ] Verify direct navigation and refresh work on login, chat-list, and chat-thread routes

### 9.6 — DNS and TLS

- [ ] Manage the application domain in Route 53 or delegate the required DNS records to Route 53
- [ ] Issue AWS Certificate Manager certificates for the frontend and API domains
- [ ] Attach the certificates to CloudFront and the ALB; expose only HTTPS publicly
- [ ] Create Route 53 alias records for the CloudFront distribution and ALB
- [ ] Update Supabase Auth redirect URLs and backend CORS origins to the final production domains

### 9.7 — GitHub Actions CI/CD

- [ ] Create a GitHub Actions OIDC identity provider and least-privilege deployment role in AWS; do not store long-lived AWS access keys in GitHub
- [ ] Add a pull-request workflow that runs backend tests, frontend tests/type-checking, the frontend build, and a backend Docker build
- [ ] Add a production backend workflow: authenticate through OIDC, build the image, push the commit-SHA tag to ECR, register a task-definition revision, and update the ECS service
- [ ] Make the backend workflow wait for ECS stability and fail when the deployment circuit breaker rolls back
- [ ] Add a production frontend workflow: build the SPA, sync assets to S3 without deleting unrelated objects, and invalidate the required CloudFront paths
- [ ] Protect the production GitHub environment, restrict deployments to the production branch, and require workflow approval if the repository supports it
- [ ] Prevent concurrent production deployments from racing by using a GitHub Actions concurrency group

### 9.8 — Observability and operational checks

- [ ] Create a CloudWatch dashboard for ALB request count/latency/4xx/5xx, unhealthy targets, and ECS CPU/memory/running-task count
- [ ] Create CloudWatch alarms for ALB 5xx responses, unhealthy targets, no running ECS tasks, deployment failure, and sustained CPU/memory pressure
- [ ] Send alarm and failed-deployment notifications through SNS email
- [ ] Verify container logs contain request/deployment context without tokens, secrets, or filing contents that should remain private
- [ ] Test failure handling: deploy an unhealthy image, confirm traffic stays on healthy tasks or rolls back, and then restore the valid revision
- [ ] Document rollback, log inspection, ECS task restart, secret rotation, and CloudFront cache invalidation commands in the deployment runbook

### 9.9 — Production release

- [ ] Supabase: re-enable email confirmation for production if disabled during development
- [ ] Run `alembic upgrade head` against production Supabase using the direct connection before deploying application code that depends on the migration
- [ ] Run ingestion against the production database and verify document/chunk counts
- [ ] Deploy the backend and frontend exclusively through GitHub Actions
- [ ] Run smoke tests against the public health endpoint, authentication flow, chat history, streaming response, and citation source panel
- [ ] End-to-end test on the deployed URLs with a real Equity Research Assistant-style email account
- [ ] Review AWS Cost Explorer, Budget status, CloudWatch alarms, and GitHub Actions deployment history after the first 24 hours

## Quick reference

| Doc | Purpose |
| --- | --- |
| `client-brief.md` | What Equity Research Assistant needs and example questions |
| `architecture.md` | System design, data model, streaming contract |
| `guides/supabase-setup.md` | Hosted Postgres + Auth |
| `guides/backend-setup.md` | FastAPI + Alembic commands |
| `guides/frontend-setup.md` | Vite + React scaffold commands |
