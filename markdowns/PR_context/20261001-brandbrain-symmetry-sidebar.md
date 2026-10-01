# Scope
- Reorganized the Brand Brain layout (`/brands`) for visual symmetry.
- Updated application shell (`app-shell`, `sidebar`, `main-shell`) to lock the sidebar in place and make only the main content area scrollable.

# Implemented Changes
- **Fixed Sidebar Layout:** Refactored `globals.css` `.app-shell` to `height: 100vh; overflow: hidden`. Both `.sidebar` and `.main-shell` now have `height: 100vh; overflow-y: auto`, isolating scroll behavior.
- **Brand Layout Refactor:** Changed `.brand-layout` from an asymmetrical `1fr 350px` grid to a symmetrical `1fr 1fr` grid. 
- **Component Splitting:** In `apps/web/components/setup.tsx`, separated the Brand Brain page into two logical columns (`.brand-col`). The left column holds the core `BrandForm`, and the right column holds the `SourceForm` (for adding knowledge) and the `Source library` list.
- **Negative Space Calibration:** Added consistent `gap: 2rem` within columns and `gap: 2.5rem` between them to elegantly control negative space.

# Architectural Decisions
- Used CSS Grid for the column split to automatically collapse gracefully onto mobile devices through the existing `max-width: 900px` media query. 
- Avoided deeply nested components to preserve React reconciliation keys on the forms.

# Verification Results
- The sidebar stays static while the middle section scrolls.
- The Brand Brain page looks balanced and premium.

# Limitations
- None.

# Next Steps
- Gather feedback on whether the workspace selector in the sidebar needs a sticky footer.
