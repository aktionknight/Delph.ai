# Simplify Web Application Metadata Title

**Date**: 2026-10-02
**Parent commit**: 9454e3a

## Scope

Simplify the browser document and metadata title in the root application layout.

## Implemented Changes

- **Root Layout Metadata (`apps/web/app/layout.tsx`)**:
  - Updated `metadata.title` from `"Delph.ai — From idea to impact"` to `"Delph.ai"`.
  - Keeps browser tab labels concise, clean, and recognizable alongside the custom Delph favicon.

## Architectural Decisions

- Clean single-word/brand titles improve legibility in narrow browser tabs without truncating dashboard routes or confusing browser tab icon alignments.

## Verification

- Verified syntax and typing with `npm --prefix apps/web run typecheck`.
- Verified pre-commit documentation checks via `python scripts/check_commit_docs.py --staged`.

## Limitations and Next Steps

- None.
