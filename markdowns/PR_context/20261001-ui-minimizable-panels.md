# Scope
Make large campaign panels minimizable and partition the scrollable area for the three content regions in the campaign workspace to fix the height of the page.

# Implemented Changes
- Converted `section.panel` for "Campaign review and fine tuning" in `ApprovalPanel` to a `<details>` element with a `<summary>` to make it minimizable.
- Converted `.canvas-generator` panel in `ContentPanel` to a `<details>` element.
- Added CSS for `details.panel` to style the summary correctly (hiding default marker and fixing layout).
- Restructured `globals.css` layout:
  - `.main-shell` is now `overflow: hidden` to prevent global scrolling issues.
  - `.main-content` is now `overflow-y: auto` to allow the page to scroll if necessary.
  - `.content-layout` is set to `height: calc(100vh - 240px)` to fit the screen vertically.
  - `.asset-list`, `.asset-main`, and `.asset-inspector` within `.content-layout` are set to `overflow-y: auto` to allow them to scroll independently.

# Architectural Decisions
- Used HTML5 `<details>` and `<summary>` elements for native collapsible behavior instead of adding React state for minimization, keeping the components simple.
- Hardcoded a responsive height calculation (`calc(100vh - 240px)`) for the content layout grid. Since `.main-content` has `overflow-y: auto`, this gracefully handles smaller screens by allowing the page to scroll while maximizing the viewport usage for the main layout.

# Next Steps
- Review with the user to see if the height constraint (240px offset) works well across their monitor resolutions.
