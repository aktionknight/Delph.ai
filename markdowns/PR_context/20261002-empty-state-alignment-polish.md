# Empty State Layout Alignment and Visual Rhythm Polish

**Date**: 2026-10-02
**Parent commit**: a172dbd

## Scope

Fix visual alignment and element hierarchy in the application empty states (such as the first-time campaign creation card), balancing line lengths, spacing, and icon centering.

## Implemented Changes

- **Empty State Container (`apps/web/app/globals.css`)**:
  - Converted `.empty` to `display: flex; flex-direction: column; align-items: center; justify-content: center;` to ensure strict horizontal and vertical centering of all children.
  - Styled `.empty-icon` as an inline-flex circular badge (`48×48px`) with `var(--accent-light)` background tint and `var(--accent)` foreground, anchoring the sparkle icon visually and eliminating optical asymmetry.
  - Added bounded max-width (`480px`) and line-height (`1.55`) to `.empty p` with a balanced bottom margin (`1.5rem`), preventing awkward single-line horizontal stretching on wide displays and providing clean breathing room before the action button.
- **Campaign Heading Text (`apps/web/components/launchpad.tsx`)**:
  - Removed an unnecessary colon before the campaign count badge in the dashboard section heading.

## Architectural Decisions

- Centralized alignment and typography improvements directly in the global `.empty` component style so all empty states across dashboard, timeline, trace, and deliverables share identical, polished hierarchy.

## Verification

- `npm --prefix apps/web run typecheck` passed with 0 errors.
- Verified staging diff and pre-commit documentation requirements via `scripts/check_commit_docs.py`.

## Limitations and Next Steps

- None.
