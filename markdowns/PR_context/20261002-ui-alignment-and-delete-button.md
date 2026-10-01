# UI Alignment Polish, Red Delete Button, and Social Analytics Refinements

**Date**: 2026-10-02
**Parent commit**: c30416f

## Scope

Refine layout alignment across the workspace header and analytics panel, update destructive button styling, enlarge the Delph brand logo, fix prop scoping in the deliverables panel, and improve LinkedIn post analytics querying.

## Implemented Changes

- **Workspace Header Navigation**:
  - `apps/web/components/campaign/workspace.tsx`: Wrapped the back navigation link and campaign deletion control in a flex container (`.workspace-nav-bar`) with `justify-content: space-between`.
  - Shifted the `Delete campaign` button to the far right, with the `← All campaigns` link on the left, vertically centered.
- **Delete Button Danger Styling**:
  - `apps/web/components/delete-control.tsx`: Switched the trigger and confirm buttons from generic secondary to `.button.danger`, accompanied by an inline `Trash2` icon.
  - `apps/web/app/globals.css`: Enhanced `.button.danger` with explicit `#ef4444` red border, background tint, text color, and focus glow to clearly indicate a destructive action. Bounded confirmation notice width and aligned it to the right.
- **Analytics Panel Alignment & Metric Cards**:
  - `apps/web/components/analytics/panel.tsx`: Moved the "Refresh social metrics" button into `.section-actions` inside `.section-heading` alongside the provenance badge, preventing full-width stretching and eliminating overlap with metric cards.
  - Added dedicated metric card icons (`Eye`, `MousePointerClick`, `Target`, `TrendingUp`) and top-row wrapper divs to match the overview dashboard styling.
  - `apps/web/app/globals.css`: Centered `.section-heading` alignment and added responsive column breakpoints to `.metric-grid`.
- **Brand Logo Resizing**:
  - `apps/web/components/launchpad.tsx`: Scaled the Delph logo image from `36×36px` to `44×44px` (~22% increase).
  - `apps/web/app/globals.css`: Proportionally adjusted `.brand-logo` typography size (`1.35rem`) and gap (`0.65rem`).
- **Deliverables Panel Prop Scope**:
  - `apps/web/components/deliverables/panel.tsx`: Passed the `isDemo` flag down from `DeliverablesPanel` through `DeliverableGroup` into `AssetDeliverables`, fixing an out-of-scope variable reference.
- **LinkedIn Analytics Querying**:
  - `apps/api/app/services/social.py`: Updated Rest.li analytics finder to use `ugc` discriminator for `urn:li:ugcPost:...` IDs, encoded entity queries safely, added `LINK_CLICKS` support, and gracefully handled unsupported 400 responses.

## Architectural Decisions

- Maintained the shared `DeleteControl` component across both campaign and asset contexts while applying universal danger styling for destructive operations.
- Retained server-side validation and confirmation modals before executing destructive deletions or social publishing requests.

## Verification

- `npm --prefix apps/web run typecheck` passed with 0 errors.
- Staged all modified files and verified pre-commit documentation hooks using `scripts/check_commit_docs.py`.

## Limitations and Next Steps

- Live social publishing and post analytics require authorized platform credentials and granted permissions.
