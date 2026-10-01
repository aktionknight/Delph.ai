# Audit: Brand and Source Removal Safeguards

**Date**: 2026-10-02
**Commit topic**: brand-source-lifecycle-and-removal
**Severity**: Low

## Findings

### 1. Cascading Data Deletion Prevention — Low (Positive Security Control)

**Evidence**: Previously, `delete_brand` iterated over all linked campaigns and assets and deleted them automatically without warning.
**Mitigation**: The endpoint now checks for existing campaigns and halts with `HTTP 409` if any are found. This guarantees that publication records, approval audit logs, and generated assets cannot be wiped out implicitly through a brand deletion call.

### 2. Client-Side Confirmation for Destructive Actions — Low

**Evidence**: Source removal previously triggered immediately on a single button click.
**Mitigation**: `SourceActions` and `RemoveBrand` now implement interactive confirmation states requiring operators to acknowledge the consequences before triggering `DELETE` mutations.

### 3. Orphaned Connection Records — Low

**Evidence**: When a brand is deleted, any third-party social connections scoped to that brand ID should not remain in active use.
**Mitigation**: `RemoveBrand` explicitly invalidates the `connections` query key upon successful deletion, prompting fresh state synchronization across the client.

## Tests Not Run

- Multi-tenant cross-account isolation tests were not re-run (covered in separate suites).
- Live cloud storage blob purge verification was not tested against external object stores.

This is a focused review of brand lifecycle safety constraints and frontend confirmation interfaces, not an exhaustive security audit.
