# Frontend API Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add validated browser configuration, a shared Supabase client, and a typed authenticated fetch client for the React frontend.

**Architecture:** `env.ts` owns all Vite environment reads, `supabase.ts` owns the single browser auth client, `http.ts` owns transport and error semantics, and `api.ts` exposes concise HTTP verbs. The modules depend in that order and remain free of product-specific endpoints.

**Tech Stack:** TypeScript 6, Vite 8, native Fetch API, `@supabase/supabase-js` 2.x

## Global Constraints

- Do not add dependencies.
- Do not add frontend test files or a test runner; `frontend/AGENTS.md` requires manual verification plus TypeScript and lint checks.
- Read `import.meta.env` only in `src/lib/env.ts`.
- Use strict TypeScript without `any`.
- Preserve all unrelated worktree changes.

---

### Task 1: Validated environment and Supabase client

**Files:**
- Create: `frontend/src/lib/env.ts`
- Create: `frontend/src/lib/supabase.ts`

**Interfaces:**
- Produces: `env: Readonly<{ apiBaseUrl: string; supabaseUrl: string; supabaseAnonKey: string }>`
- Produces: `supabase`, the shared result of `createClient(env.supabaseUrl, env.supabaseAnonKey)`

- [ ] **Step 1: Implement required string validation**

Create a helper with signature `required(name: keyof ImportMetaEnv): string`. Trim the value and throw `Error("Missing required environment variable: " + name)` when empty.

- [ ] **Step 2: Implement URL validation**

Create `requiredHttpUrl(name: "VITE_API_BASE_URL" | "VITE_SUPABASE_URL"): string`. Parse with `new URL`, accept only `http:` and `https:`, remove trailing slashes from the returned value, and throw `Error("Invalid HTTP URL in environment variable: " + name)` for invalid values.

- [ ] **Step 3: Export validated config and browser client**

Export a frozen `env` object with camel-cased properties and create one Supabase client from it using the library defaults.

- [ ] **Step 4: Type-check the modules**

Run: `pnpm tsc --noEmit`
Expected: exit code 0.

### Task 2: Typed authenticated HTTP transport

**Files:**
- Create: `frontend/src/lib/http.ts`

**Interfaces:**
- Consumes: `env.apiBaseUrl` and `supabase.auth.getSession()`
- Produces: `ApiError`, `RequestOptions`, and `request<T>(path: string, options?: RequestOptions): Promise<T>`

- [ ] **Step 1: Define transport types and errors**

Define `RequestOptions` as `Omit<RequestInit, "body"> & { body?: BodyInit | Record<string, unknown> | unknown[] | null; timeoutMs?: number }`. Define `ApiError extends Error` with readonly `status?: number`, `body?: unknown`, and `isNetworkError: boolean` fields.

- [ ] **Step 2: Build request headers and body**

Copy caller headers into `Headers`, retrieve the current Supabase session, and set the current bearer token when present. Pass through native `BodyInit` values; JSON-stringify plain objects and arrays and set the JSON content type if absent.

- [ ] **Step 3: Implement URL, timeout, and response handling**

Resolve relative paths under `env.apiBaseUrl`, abort after a default 15 seconds, parse JSON by content type, return `undefined` for `204` or an empty body, and return text otherwise. Throw `ApiError` for non-2xx responses with the parsed body and status.

- [ ] **Step 4: Normalize transport failures**

Re-throw existing `ApiError` values. Convert aborts to `ApiError("Request timed out", { isNetworkError: true })` and other fetch failures to `ApiError("Network request failed", { isNetworkError: true })`. Always clear the timeout.

- [ ] **Step 5: Type-check the transport**

Run: `pnpm tsc --noEmit`
Expected: exit code 0.

### Task 3: Generic API singleton and full verification

**Files:**
- Create: `frontend/src/lib/api.ts`

**Interfaces:**
- Consumes: `request<T>` and `RequestOptions`
- Produces: `api.get<T>`, `api.post<T>`, `api.put<T>`, `api.patch<T>`, and `api.delete<T>`

- [ ] **Step 1: Implement generic methods**

Each method delegates to `request<T>` with its HTTP method. Body methods accept `RequestOptions["body"]`; all methods accept optional remaining request options. Do not add product-specific routes.

- [ ] **Step 2: Run static checks**

Run: `pnpm tsc --noEmit`
Expected: exit code 0.

Run: `pnpm lint`
Expected: exit code 0.

- [ ] **Step 3: Build production assets**

Run: `pnpm build`
Expected: TypeScript and Vite complete with exit code 0.

- [ ] **Step 4: Review the diff**

Run: `git diff --check` and inspect only the new plan and four library modules. Confirm no dependency or unrelated file changed.
