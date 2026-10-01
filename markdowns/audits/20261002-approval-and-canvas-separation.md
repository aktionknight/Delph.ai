# Audit: Approval and Canvas Separation

**Date**: 2026-10-02
**Commit topic**: approval-and-canvas-separation
**Severity**: Low

## Findings

### 1. Read-only enforcement in approval mode — Low

**Evidence**: When `approvalsOnly` is true, the form inputs are wrapped in a `<fieldset disabled={busy || approvalsOnly}>` and action buttons (`Save and evaluate`, `Revise`, `Generate static`, `Generate narration`) are removed from rendering.
**Mitigation**: The backend API remains the authoritative boundary: modifying asset copy requires calling the update endpoint (which resets approval status), and publication strictly requires passing evaluations and explicit approval records matching the target asset version. The frontend UI restriction ensures users do not accidentally make or expect unrecorded in-place edits while in approval mode.

### 2. Client-side state synchronization on tab toggle — Low

**Evidence**: `AssetEditor` receives `approvalsOnly` as a boolean prop. If unsaved edits existed in the editor before navigating between tabs, state could theoretically linger if components were preserved.
**Mitigation**: The parent key in `ContentPanel` relies on `${selected.id}-${selected.current_version}`. In addition, `ContentPanel` only allows editing in the Content Canvas tab, ensuring the approval view cleanly inspects saved version states.

## Tests Not Run

- End-to-end browser automation suite was not run during this commit.
- External social network publishing APIs were not invoked live.

This is a focused review of user interface separation and component state handling, not an exhaustive security audit.
