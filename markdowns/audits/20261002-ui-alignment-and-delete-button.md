# Audit: UI Alignment, Red Delete Button, and Social Analytics

**Date**: 2026-10-02
**Commit topic**: ui-alignment-and-delete-button
**Severity**: Low

## Findings

### 1. Destructive action prominence and accidental triggers — Low

**Evidence**: The delete campaign and asset action previously shared the same neutral `.button.secondary` styling as non-destructive buttons.
**Mitigation**: The button is now styled with `.button.danger` in red and includes a `Trash2` icon. The confirmation dialog requirement is preserved, requiring explicit double-confirmation before sending any `DELETE` API request.

### 2. LinkedIn analytics entity query format — Low

**Evidence**: LinkedIn memberCreatorPostAnalytics expects `ugc` rather than `ugcPost` in the entity finder parameter `(ugc:urn:li:ugcPost:...)`. Unhandled query type failures previously caused exceptions.
**Mitigation**: Updated the query builder discriminator and handled HTTP 400 responses gracefully by marking unsupported query types as `None` without aborting remaining metric collection.

### 3. Client-side scope safety in deliverables view — Low

**Evidence**: An unpassed `me` variable reference in `AssetDeliverables` broke TypeScript compilation when accessing workspace demo mode status.
**Mitigation**: Passed `isDemo` explicitly from the parent query down through component props, ensuring type-safe rendering of publishing capabilities.

## Tests Not Run

- Live LinkedIn social API calls were not executed against live production endpoints.
- End-to-end browser deletion automation was not executed.

This is a focused review of interface layout adjustments, styling modifications, and query parameter encoding, not an exhaustive security audit.
