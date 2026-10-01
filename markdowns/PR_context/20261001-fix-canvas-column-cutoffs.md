# Scope
- Fix the issue where the left and right sidebars in the Content Canvas tab were getting cut off at the bottom while the middle column stretched to full height.

# Implemented Changes
- Removed `max-height: calc(100vh - 180px)` and `overflow-y: auto` from `.asset-list` and `.asset-inspector` in `apps/web/app/globals.css`.
- Removed sticky positioning so all three columns (`.asset-list`, `.asset-main`, and `.asset-inspector`) flow naturally down together to the bottom of the container without clipping or inner scroll traps.

# Architectural Decisions
- With the middle editor already segmented into tabs, the total height of `.asset-main` is compact and fits naturally on screen. Removing artificial max-height limits on the sidebars allows all three columns to render completely without prematurely truncating cards or review history.

# Verification Results
- No cutoff content in left or right sidebars.
- Bottom alignment is consistent across all 3 grid columns.

# Limitations
- None.

# Next Steps
- None.
