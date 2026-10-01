# Brand Brain and Source Lifecycle with Protected Deletion

**Date**: 2026-10-02
**Parent commit**: ca18ced

## Scope

Implement brand and source removal safeguards in Brand Brain, preventing accidental cascading deletion of campaigns and publication history while providing double-confirmation dialogs for deleting sources and brands.

## Implemented Changes

- **Backend Safeguards (`apps/api/app/api/routes.py`)**:
  - `DELETE /brands/{brand_id}`: Checked for existing campaigns linked to the brand. If any exist, returns `HTTP 409 Conflict` with explicit messaging instructing the operator to delete campaigns first, preserving campaign audit trails and publication records from accidental cascading loss.
- **Workflow Tests (`apps/api/tests/test_workflow.py`)**:
  - Added `test_brand_and_source_lifecycle_preserves_campaigns` verifying that source deletion succeeds, brand deletion with active campaigns fails with 409, and brand deletion succeeds after its campaigns are removed.
- **Brand Removal Component (`apps/web/components/context/remove-brand.tsx`)**:
  - Added `RemoveBrand` panel in Brand Brain with red `.button.danger` trigger, double-confirmation step explaining the permanence of deletion, and query cache invalidation on completion.
- **Source Removal Confirmation (`apps/web/components/context/source-actions.tsx`)**:
  - Added a two-step confirmation dialog with `Keep source` and `Confirm removal` (`.button.danger`) before sending `DELETE` requests to remove source documents from the library.
- **Brand Brain Layout (`apps/web/components/setup.tsx`)**:
  - Embedded `RemoveBrand` in the Brand Brain management column alongside the brand editor form.

## Architectural Decisions

- Disallowed implicit cascading deletion of campaigns when deleting brands. Campaigns contain immutable human approvals, generation traces, and live published post links that must not be destroyed silently.
- Required explicit client confirmation for both source document removal and brand removal.

## Verification

- `pytest apps/api/tests/test_workflow.py -k test_brand_and_source_lifecycle_preserves_campaigns` passed.
- `npm --prefix apps/web run typecheck` passed with 0 errors.
- Verified commit documentation rules via `scripts/check_commit_docs.py`.

## Limitations and Next Steps

- Deleting a brand is permanent once its campaigns are cleared.
- Already published social posts remain online and cannot be pulled automatically upon brand deletion.
