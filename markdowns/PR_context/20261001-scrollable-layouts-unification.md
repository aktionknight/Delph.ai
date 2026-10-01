# Scope
Implement scrollable divisions in all primary multi-column layouts across the application (e.g., Strategy layout, Brand layout, Analytics layout) to match the fixed-height scrollable partitioning pattern established for the Content Canvas.

# Implemented Changes
- Updated `.strategy-layout` and `.form-layout` to use `height: calc(100vh - 240px)` and `align-items: stretch`.
- Added `overflow-y: auto` to direct children of `.strategy-layout` and `.form-layout`.
- Updated `.brand-layout` to use `height: calc(100vh - 200px)` (tighter header allowance) and `align-items: stretch`.
- Added `overflow-y: auto` to `.brand-col` children of `.brand-layout`.
- Updated `.analytics-layout` to use `height: calc(100vh - 380px)` (due to large metric grid above) and `align-items: stretch`.
- Added `overflow-y: auto` to direct children of `.analytics-layout`.
- Added `padding-right: 0.5rem` to all scrollable columns to avoid scrollbar overlap with content.

# Architectural Decisions
- Extended the `calc(100vh - offset)` strategy across all main CSS grid layouts rather than rewriting the component DOM structure. This safely restricts the page height while keeping the main container layout responsive. 
- Relying on the parent `.main-content` possessing `overflow-y: auto` as a fallback ensures that if viewports are too small for the calculated height, the full page can still scroll gracefully without breaking the UI.

# Next Steps
- Verify if any grid elements within `.form-layout` on user account pages need additional height tuning.
