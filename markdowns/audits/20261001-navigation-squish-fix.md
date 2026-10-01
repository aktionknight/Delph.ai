# Security & Correctness Audit

## Review of Changes
- Added a CSS rule to prevent `flex-shrink` on direct children of `.main-content`.

## Potential Flaws & Vulnerabilities
- **Severity: None.** This is a standard CSS flexbox adjustment to prevent visual distortion of block-level UI components. It does not introduce layout breaking changes since `overflow-y: auto` is already present on the parent container to handle any resulting overflow gracefully.
- No security, data, or state management implications.

## Mitigations
- Targeted specifically at direct children `> *` so it doesn't accidentally prevent intended flex-shrinking inside deeply nested components like forms or asset lists.

## Tests Not Run
- Not tested visually across multiple browsers, but `flex-shrink: 0` is universally supported behavior in CSS Flexbox.
