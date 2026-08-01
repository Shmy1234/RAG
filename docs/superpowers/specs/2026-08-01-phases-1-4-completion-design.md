# Phases 1–4 Completion Design

## Goal

Make Phases 1–4 reproducible after a Supabase reset and ensure the checklist reports only verified work.

## Design

Keep the existing architecture. Phase 4 remains a two-stage local pipeline: SEC HTML in `data/downloads/` is converted to persistent normalized Markdown in `data/Markdown/`, then the backend CLI chunks, embeds, and uploads that Markdown. The converter must never publish a manifest entry whose Markdown output is missing. The ingestion CLI remains dry-run by default and requires explicit `--upload`; full-corpus uploads additionally require `--yes`.

Phase 1–3 code is retained because its unit, type, and lint checks pass. Live Supabase-dependent items remain unchecked until migrations, authentication, authorization, streaming, and persistence are exercised against the replacement project.

## Verification

- Unit-test conversion path rewriting and failure-safe manifest generation.
- Run converter tests, backend tests, Ruff, TypeScript, and ESLint.
- Run one-document ingestion dry-run without network writes.
- Document the exact reset sequence and paid upload gates.
