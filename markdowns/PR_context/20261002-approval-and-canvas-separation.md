# Separate Content Creation and Approval Workflows

**Date**: 2026-10-02
**Parent commit**: ec5c4a8

## Scope

Remove functional redundancy between the Content Canvas and the Approvals section by enforcing a strict separation of concerns: Content Canvas handles draft creation, editing, and media generation, while the Approvals panel handles reviewing and decisioning (approving, requesting changes, or rejecting).

## Implemented Changes

- `apps/web/components/canvas/panel.tsx`: Passed the `approvalsOnly` flag down to `AssetEditor` when rendering assets in the Approvals tab.
- `apps/web/components/canvas/asset-editor.tsx`:
  - Added `approvalsOnly?: boolean` prop to `AssetEditor`.
  - In Content Canvas mode (`!approvalsOnly`): Hides the Stage 05 human review approval action panel (approve / request changes / reject buttons) while keeping full access to draft editing, AI copy revision, static image generation, and audio narration synthesis.
  - In Approvals mode (`approvalsOnly === true`): Displays the Stage 05 human review panel for formal sign-off, while disabling text field modifications (`disabled={busy || approvalsOnly}`) and omitting the save button, AI revision triggers, and media generation prompts/buttons. Reviewers still see all version previews, media players, and rule-based evaluation issue logs.

## Architectural Decisions

- Preserved the shared `AssetEditor` component architecture to avoid diverging preview layouts and styling between editing and approval workflows, controlled cleanly via the `approvalsOnly` flag.
- Enforced read-only behavior in approval mode by disabling fieldsets and hiding generation controls, ensuring reviewers inspect immutable version states rather than editing in place without re-evaluating.
- Preserved historical review logs in both views for full audit transparency.

## Verification

- Verified `ContentPanel` prop plumbing and conditional rendering logic in `AssetEditor`.
- Checked TypeScript compilation for `apps/web`.
- Staged changes and verified git hook compliance via `scripts/check_commit_docs.py`.

## Limitations and Next Steps

- Backend validation already rejects unauthorized publishing and requires approval on the current asset version.
- Future enhancements could provide side-by-side version comparison diffs directly within the approval review panel.
