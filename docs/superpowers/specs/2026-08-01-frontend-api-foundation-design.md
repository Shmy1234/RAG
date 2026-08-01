# Frontend API Foundation Design

## Scope

Implement the frontend foundation for validated runtime configuration, Supabase browser authentication, and authenticated JSON requests to the FastAPI backend. Product-specific endpoint functions are intentionally deferred until their backend contracts exist.

## Modules

### `src/lib/env.ts`

This is the only frontend module that reads `import.meta.env`. It validates `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` at module load, trims surrounding whitespace, and throws a clear error naming any missing variable. Both URL values must be valid absolute HTTP or HTTPS URLs. The module exports one immutable `env` object.

### `src/lib/supabase.ts`

Create and export one browser Supabase client using the validated project URL and anon key. Authentication session persistence and refresh behavior use the browser-oriented defaults from `@supabase/supabase-js`.

### `src/lib/http.ts`

Provide the low-level typed request function and `ApiError` type. Each request obtains the current Supabase session immediately before calling `fetch` and adds an `Authorization: Bearer <access-token>` header when a session exists. Caller-provided headers are preserved, except that the current bearer token remains authoritative.

The wrapper joins relative paths to the configured backend base URL, serializes non-`FormData` request bodies as JSON, and sets `Content-Type: application/json` when needed. It parses JSON responses when indicated by the response content type, returns `undefined` for empty responses, and preserves text responses otherwise.

Requests use a finite timeout through `AbortController`. HTTP failures throw `ApiError` with the status and parsed response body. Timeout and fetch/network failures throw `ApiError` with `status` unset and `isNetworkError` set to `true`, allowing UI code to distinguish connectivity and CORS failures from backend responses.

### `src/lib/api.ts`

Export a singleton with generic typed `get`, `post`, `put`, `patch`, and `delete` methods. These methods delegate to the HTTP wrapper and do not contain product-specific routes.

## Error Behavior

- Missing or invalid configuration fails immediately during application startup.
- An absent Supabase session does not prevent a request; it is sent without an authorization header so the backend remains responsible for returning `401` where required.
- Non-2xx responses throw `ApiError` and preserve the backend response payload for display or inspection.
- Timeouts and browser-level fetch failures are marked as network errors.

## Verification

The frontend repository explicitly prohibits adding a test runner or test files. Verification therefore uses the repository-prescribed checks:

1. `pnpm tsc --noEmit`
2. `pnpm lint`
3. `pnpm build`

The implementation stays dependency-free beyond the already-installed Supabase client and native browser APIs.
