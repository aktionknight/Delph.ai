# Security and Quality Audit: Canvas Scrolling

## Scope
Reviewing CSS layout overrides in `globals.css` targeting Canvas UI `.content-layout` scrolling behavior.

## Findings

1. **UX and Layout Stability**
   - **Severity:** Low
   - **Evidence:** Fixed height calculation limits `.content-layout` to fit the viewport vertically, preventing the parent page from stretching to match the massive internal content of `.asset-main`. The `overflow-y: auto` property on the columns gracefully delegates scrolling.
   - **Mitigation:** The custom `-webkit-scrollbar` styling applies only to those specific canvas columns, preventing side-effects on global browser scrollbars. 

## Tests Not Run
- Explicit boundary tests on 1080p vs 4k monitors. The `calc(100vh - 260px)` acts as a functional approximation for the viewport minus the app header / generator bar.

## Conclusion
Approved. Safe for merge.
