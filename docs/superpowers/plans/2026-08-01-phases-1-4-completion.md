# Phases 1–4 Completion Implementation Plan

> **For agentic workers:** Execute inline; do not dispatch subagents. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct Phase 4 pipeline safety and documentation, then verify all locally testable Phase 1–4 requirements.

**Architecture:** Preserve the existing two-stage HTML→Markdown→database pipeline. Add strict conversion/manifest boundaries and keep paid or live external operations explicit.

**Tech Stack:** Python 3.12, Docling, FastAPI, pytest, Ruff, React, TypeScript, Supabase, OpenAI.

## Global Constraints

- No subagents.
- No new dependencies.
- Do not make paid OpenAI calls or full database uploads automatically.
- Do not mark live Supabase checks complete without evidence.

### Task 1: Make conversion manifests failure-safe

**Files:**
- Modify: `data/html_to_markdown/convert_html_to_markdown.py`
- Modify: `data/html_to_markdown/test_convert_html_to_markdown.py`

- [x] Add failing tests for missing Markdown outputs and invalid source manifest paths.
- [x] Implement manifest validation and stable SEC item headings.
- [x] Run converter tests.

### Task 2: Correct workflow documentation and checklist

**Files:**
- Modify: `data/README.md`
- Modify: `README.md`
- Modify: `docs/todos.md`

- [x] Document download, conversion, dry-run, smoke upload, and full upload commands.
- [x] Ensure live verification items remain unchecked.

### Task 3: Verify Phases 1–4 locally

- [x] Run converter tests and backend tests.
- [x] Run Ruff for Phases 1–4 (the full suite has two pre-existing Phase 5 test lint findings).
- [x] Run frontend TypeScript and ESLint checks.
- [x] Run one-document ingestion dry-run.
- [x] Review diff and record remaining live Supabase actions in `docs/todos.md`.
